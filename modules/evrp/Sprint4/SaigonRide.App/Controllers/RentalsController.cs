using System.Security.Claims;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.SignalR;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Hubs;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;
using SaigonRide.App.Services;

namespace SaigonRide.App.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    [Authorize(AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme)]
    public class RentalsController : ControllerBase
    {
        private readonly AppDbContext _context;
        private readonly SepayService _sepayService;
        private readonly IWebHostEnvironment _env;
        private readonly IHubContext<RentalHub> _rentalHub;
        private readonly IHubContext<AdminHub> _adminHub;

        
        public RentalsController(
            AppDbContext context,
            SepayService sepayService,
            IWebHostEnvironment env,
            IHubContext<RentalHub> rentalHub,
            IHubContext<AdminHub> adminHub)
        {
            _context = context;
            _sepayService = sepayService;
            _env = env;
            _rentalHub = rentalHub;
            _adminHub = adminHub;
        }

        // ─── START RENTAL ──────────────────────────────────────────────────────────
        [HttpPost("start")]
        public async Task<IActionResult> StartRental([FromBody] RentalRequest request)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            // 1. One active/pending rental limit per user
            if (_env.IsDevelopment())
            {
                await CancelOpenRentalsForUser(userId);
            }
            else
            {
                var hasActiveRental = await _context.Rentals
                    .AnyAsync(r => r.UserId == userId &&
                                   (r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending));

                if (hasActiveRental)
                    return BadRequest(new { Message = "You already have an active or pending rental." });
            }

            // 2. Availability check
            var vehicle = await _context.Vehicles.FindAsync(request.VehicleId);
            if (vehicle == null) return NotFound(new { Message = "Vehicle not found." });

            // Robust Fix: Ensure the vehicle is actually at a station before renting
            if (!vehicle.StationId.HasValue)
                return BadRequest(new { Message = "Vehicle location error: This vehicle is not currently assigned to a station." });

            if (!vehicle.IsActive || vehicle.Status == VehicleStatus.Maintenance ||
                vehicle.Status == VehicleStatus.OutOfService)
                return BadRequest(new { Message = "Vehicle is not available for rent." });

            var vehicleOccupied = await _context.Rentals
                .AnyAsync(r => r.VehicleId == request.VehicleId &&
                               (r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending));
            if (vehicleOccupied)
                return BadRequest(new { Message = "Vehicle is currently unavailable." });

            // 3. Calculate Deposit based on Grade
            decimal depositPercentage = vehicle.Grade switch
            {
                VehicleGrade.GradeA => 0.20m,
                VehicleGrade.GradeB => 0.15m,
                VehicleGrade.GradeC => 0.10m,
                _ => 0.15m
            };
            decimal calculatedDeposit = vehicle.MarketValue * depositPercentage;

            // --- TRANSACTION START ---
            using var transaction = await _context.Database.BeginTransactionAsync();
            try
            {
                // Robust Fix: Use .Value safely since we checked .HasValue above.
                // Also handles request.Mode if it arrives as null from the frontend.
                var newRental = new Rental
                {
                    UserId = userId,
                    VehicleId = vehicle.Id,
                    Mode = request.Mode,
                    Status = RentalStatus.Pending,
                    StartStationId = vehicle.StationId.Value 
                };

                var newDeposit = new Deposit
                {
                    Rental = newRental,
                    Amount = calculatedDeposit,
                    Status = DepositStatus.Pending,
                    CreatedAt = DateTime.UtcNow
                };

                _context.Rentals.Add(newRental);
                _context.Deposits.Add(newDeposit);
                await _context.SaveChangesAsync();

                // 4. Generate the VietQR Image URL via SepayService
                string qrImageUrl = _sepayService.GenerateQrUrl(calculatedDeposit, newRental.Id);

                await transaction.CommitAsync();

                return Ok(new
                {
                    Message = "Rental initiated. Please scan the QR code on the screen to pay the deposit.",
                    RentalId = newRental.Id,
                    QrUrl = qrImageUrl,
                    DepositAmount = calculatedDeposit
                });
            }
            catch (Exception ex)
            {
                await transaction.RollbackAsync();
                return StatusCode(500, new { Message = "Error initiating rental.", Details = ex.Message });
            }
        }

        // ─── STATUS FOR KIOSK POLLING ─────────────────────────────────────────────
        [HttpGet("{id}/status")]
        public async Task<IActionResult> GetRentalStatus(int id)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var rental = await _context.Rentals
                .Include(r => r.Vehicle)
                .Where(r => r.Id == id && r.UserId == userId)
                .Select(r => new {
                    r.Id,
                    r.Status,
                    vehicleCode = r.Vehicle.LicensePlate ?? r.Vehicle.Name,
                    dockId = "Dock" + r.StartStationId.ToString()
                })
                .FirstOrDefaultAsync();

            if (rental == null) return NotFound();

            return Ok(new {
                status = rental.Status.ToString(),
                vehicleCode = rental.vehicleCode,
                dockId = rental.dockId
            });
        }

        [HttpGet("{id}/return-status")]
        public async Task<IActionResult> GetReturnStatus(int id)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var email = User.FindFirstValue(ClaimTypes.Email);
            var isKioskOrAdmin = User.IsInRole("Admin") || email == "kiosk@saigonride.com";

            var query = _context.Rentals
                .Include(r => r.Vehicle)
                .Include(r => r.Deposit)
                .Where(r => r.Id == id);

            if (!isKioskOrAdmin)
            {
                query = query.Where(r => r.UserId == userId);
            }

            var rental = await query.FirstOrDefaultAsync();

            if (rental == null) return NotFound();

            if (rental.Status != RentalStatus.Completed)
            {
                return Ok(new { status = rental.Status.ToString() });
            }

            decimal baseFare = rental.TotalCost;
            decimal discount = 0;
            decimal finalFare = rental.TotalCost;
            string depositNote = rental.Deposit?.Status == DepositStatus.Refunded 
                ? $"Hoàn cọc: {rental.Deposit.Amount:N0} VNĐ" 
                : "Không có cọc hoàn trả";

            return Ok(new {
                status = "Completed",
                summary = new {
                    baseFare = baseFare,
                    discount = discount,
                    finalFare = finalFare,
                    depositNote = depositNote
                }
            });
        }
        // ─── RETURN RENTAL ────────────────────────────────────────────────────────
        [HttpPost("return/{rentalId}")]
        public async Task<IActionResult> ReturnRental(int rentalId)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var rental = await _context.Rentals
                .Include(r => r.Vehicle)
                .Include(r => r.Deposit)
                .FirstOrDefaultAsync(r => r.Id == rentalId);

            if (rental == null)
                return NotFound(new { Message = "Rental record not found." });

            if (rental.Status != RentalStatus.Active)
                return BadRequest(new { Message = "This rental is not currently active." });

            if (rental.StartTime == null)
                return BadRequest(new { Message = "Rental has not started yet." });

            using var transaction = await _context.Database.BeginTransactionAsync();
            try
            {
                rental.EndTime = DateTime.UtcNow;
                var duration = rental.EndTime.Value - rental.StartTime.Value;

                decimal totalCost = 0;
                if (rental.Mode == RentalMode.Hourly)
                {
                    var billedHours = (decimal)Math.Ceiling(duration.TotalHours);
                    if (billedHours < 1) billedHours = 1;
                    totalCost = billedHours * rental.Vehicle.HourlyRate;
                }
                else
                {
                    var billedDays = (decimal)Math.Ceiling(duration.TotalDays);
                    if (billedDays < 1) billedDays = 1;
                    totalCost = billedDays * rental.Vehicle.DailyRate;
                }

                rental.TotalCost = totalCost;
                rental.Status = RentalStatus.Completed;
                rental.Vehicle.Status = VehicleStatus.Available;

                if (rental.Deposit != null)
                {
                    rental.Deposit.Status = DepositStatus.Refunded;
                    rental.Deposit.ProcessedAt = DateTime.UtcNow;
                }

                await _context.SaveChangesAsync();
                await transaction.CommitAsync();
                await NotifyRentalStatusChanged(rental);

                return Ok(new
                {
                    rentalId = rental.Id,
                    Message = "Vehicle returned successfully!",
                    Duration = $"{duration.Hours}h {duration.Minutes}m",
                    FinalCost = totalCost,
                    DepositStatus = "Refunded"
                });
            }
            catch (Exception)
            {
                await transaction.RollbackAsync();
                return StatusCode(500, new { Message = "Error processing return." });
            }
        }
        [HttpPost("return")]
        public async Task<IActionResult> ReturnByBikeCode([FromBody] ReturnByCodeRequest request)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var vehicle = await _context.Vehicles
                .FirstOrDefaultAsync(v => v.LicensePlate == request.BikeCode || v.Name == request.BikeCode);
            if (vehicle == null)
                return NotFound(new { message = "Vehicle not found." });

            var rental = await _context.Rentals
                .Include(r => r.Vehicle)
                .FirstOrDefaultAsync(r => r.VehicleId == vehicle.Id && r.Status == RentalStatus.Active);
            if (rental == null)
                return NotFound(new { message = "No active rental found for this vehicle." });

            return await ReturnRental(rental.Id);            
        }

        // ─── RENTAL HISTORY ───────────────────────────────────────────────────────
        [HttpGet("history")]
        public async Task<IActionResult> GetHistory()
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var history = await _context.Rentals
                .Include(r => r.Vehicle)
                .Include(r => r.Deposit)
                .Where(r => r.UserId == userId)
                .OrderByDescending(r => r.Id)
                .Select(r => new RentalHistoryViewModel
                {
                    RentalId = r.Id,
                    VehicleName = r.Vehicle.Name,
                    StartTime = r.StartTime.HasValue ? r.StartTime.Value.ToString("yyyy-MM-dd HH:mm") : "Pending",
                    EndTime = r.EndTime.HasValue ? r.EndTime.Value.ToString("yyyy-MM-dd HH:mm") : "Ongoing",
                    Status = r.Status.ToString(),
                    TotalCost = r.TotalCost,
                    DepositAmount = r.Deposit != null ? r.Deposit.Amount : 0
                })
                .ToListAsync();

            return Ok(history);
        }

        // ─── CANCEL PENDING RENTAL ────────────────────────────────────────────────
        [HttpDelete("{id}/cancel")]
        public async Task<IActionResult> CancelRental(int id)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var rental = await _context.Rentals
                .Include(r => r.Deposit)
                .FirstOrDefaultAsync(r => r.Id == id);

            if (rental == null) return NotFound(new { Message = "Rental not found." });
            if (rental.UserId != userId) return Forbid();
            if (rental.Status != RentalStatus.Pending)
                return BadRequest(new { Message = "Only pending rentals can be cancelled." });

            rental.Status = RentalStatus.Cancelled;
            if (rental.Deposit != null)
            {
                rental.Deposit.Status = DepositStatus.Cancelled;
                rental.Deposit.ProcessedAt = DateTime.UtcNow;
            }

            await _context.SaveChangesAsync();
            await NotifyRentalStatusChanged(rental);
            return Ok(new { Message = "Rental cancelled." });
        }

        private async Task CancelOpenRentalsForUser(string userId)
        {
            var openRentals = await _context.Rentals
                .Include(r => r.Deposit)
                .Include(r => r.Vehicle)
                .Where(r => r.UserId == userId &&
                            (r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending))
                .ToListAsync();

            foreach (var rental in openRentals)
            {
                rental.Status = RentalStatus.Cancelled;
                rental.EndTime ??= DateTime.UtcNow;

                if (rental.Deposit != null)
                {
                    rental.Deposit.Status = DepositStatus.Cancelled;
                    rental.Deposit.ProcessedAt ??= DateTime.UtcNow;
                }

                rental.Vehicle.Status = VehicleStatus.Available;
                rental.Vehicle.StationId ??= rental.StartStationId;
            }

            if (openRentals.Count > 0)
            {
                await _context.SaveChangesAsync();
                foreach (var rental in openRentals)
                {
                    await NotifyRentalStatusChanged(rental);
                }
            }
        }

        private async Task NotifyRentalStatusChanged(Rental rental)
        {
            var vehicleCode = rental.Vehicle?.LicensePlate ?? rental.Vehicle?.Name;
            var dockId = "Dock" + rental.StartStationId.ToString();

            await RentalHub.NotifyRentalStatusChanged(
                _rentalHub,
                rental.Id,
                rental.UserId, // add this
                rental.Status.ToString(),
                vehicleCode,
                dockId);
        }   
    }
    public record ReturnByCodeRequest(string BikeCode, int EndStationId = 2);
}
