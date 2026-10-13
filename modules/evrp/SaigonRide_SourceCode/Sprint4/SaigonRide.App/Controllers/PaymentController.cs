using System.Security.Claims; 
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.SignalR;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Helpers;
using SaigonRide.App.Hubs;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;

namespace SaigonRide.App.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class PaymentController : ControllerBase
    {
        private readonly AppDbContext _context;
        private readonly IConfiguration _config;
        private readonly IHubContext<RentalHub> _rentalHub;
        private readonly IHubContext<AdminHub> _adminHub;

        public PaymentController(
            AppDbContext context,
            IConfiguration config,
            IHubContext<RentalHub> rentalHub,
            IHubContext<AdminHub> adminHub)
        {
            _context = context;
            _config = config;
            _rentalHub = rentalHub;
            _adminHub = adminHub;
        }

        // ─── SEPAY WEBHOOK ────────────────────────────────────────────────────────

        [HttpPost("sepay-return")]
        public async Task<IActionResult> SepayReturn([FromBody] SePayWebhookPayload payload)
        {
            if (!VerifySepaySignature())
                return Unauthorized(new { message = "Invalid or missing API key" });

            if (payload.transferType != "in")
                return Ok(new { success = true, message = "Ignored: outgoing transfer" });

            var match = Regex.Match(payload.content, @"\bSGR\s+(\d+)\b", RegexOptions.IgnoreCase);
            if (!match.Success)
                return Ok(new { success = true, message = "Ignored: no valid SGR code in content" });

            int rentalId = int.Parse(match.Groups[1].Value);

            var rental = await _context.Rentals
                .Include(r => r.Vehicle)
                .Include(r => r.Deposit)
                .Include(r => r.StartStation)
                .FirstOrDefaultAsync(r => r.Id == rentalId);

            if (rental == null)
                return Ok(new { success = true, message = $"Ignored: rental {rentalId} not found" });

            if (rental.Status != RentalStatus.Pending)
                return Ok(new { success = true, message = "Ignored: rental already processed" });

            using var transaction = await _context.Database.BeginTransactionAsync();
            try
            {
                rental.Status = RentalStatus.Active;
                rental.StartTime = DateTime.UtcNow;
                rental.Vehicle.Status = VehicleStatus.Rented;

                if (rental.Deposit != null)
                {
                    rental.Deposit.Status = DepositStatus.Held;
                    rental.Deposit.Note = $"Paid via SePay (Ref: {payload.referenceCode})";
                    rental.Deposit.ProcessedAt = DateTime.UtcNow;
                }

                await _context.SaveChangesAsync();
                await transaction.CommitAsync();
                await NotifyRentalActivated(rental);

                return Ok(new { success = true, message = "Payment confirmed. Rental is now active.", rentalId });
            }
            catch (Exception ex)
            {
                await transaction.RollbackAsync();
                return StatusCode(500, new { success = false, message = "Database error", error = ex.Message });
            }
        }

        // ─── VNPAY RETURN ─────────────────────────────────────────────────────────

        [HttpGet("vnpay-return")]
        public async Task<IActionResult> VnpayReturn()
        {
            if (!Request.Query.Any())
                return Redirect("/Home/Error?reason=no_data");

            string hashSecret = _config["Vnpay:HashSecret"]!;
            var vnpay = new VnPayLibrary();

            foreach (var (key, value) in Request.Query)
            {
                if (!string.IsNullOrEmpty(key) && key.StartsWith("vnp_"))
                    vnpay.AddResponseData(key, value!);
            }

            string secureHash = Request.Query["vnp_SecureHash"]!;
            if (!vnpay.ValidateSignature(secureHash, hashSecret))
                return Redirect("/Home/Error?reason=invalid_signature");

            string responseCode = vnpay.GetResponseData("vnp_ResponseCode");
            string txnStatus = vnpay.GetResponseData("vnp_TransactionStatus");

            if (responseCode != "00" || txnStatus != "00")
                return Redirect($"/Home/Error?reason=payment_failed&code={responseCode}");

            if (!int.TryParse(vnpay.GetResponseData("vnp_TxnRef"), out int rentalId))
                return Redirect("/Home/Error?reason=invalid_rental");

            var rental = await _context.Rentals
                .Include(r => r.Vehicle)
                .Include(r => r.Deposit)
                .Include(r => r.StartStation)
                .FirstOrDefaultAsync(r => r.Id == rentalId);

            if (rental == null || rental.Status != RentalStatus.Pending)
                return Redirect($"/Rentals/Detail/{rentalId}");

            using var transaction = await _context.Database.BeginTransactionAsync();
            try
            {
                rental.Status = RentalStatus.Active;
                rental.StartTime = DateTime.UtcNow;
                rental.Vehicle.Status = VehicleStatus.Rented;

                if (rental.Deposit != null)
                {
                    rental.Deposit.Status = DepositStatus.Held;
                    rental.Deposit.ProcessedAt = DateTime.UtcNow;
                }

                await _context.SaveChangesAsync();
                await transaction.CommitAsync();
                await NotifyRentalActivated(rental);

                return Redirect($"/Rentals/Detail/{rentalId}?payment=success");
            }
            catch
            {
                await transaction.RollbackAsync();
                return Redirect("/Home/Error?reason=db_error");
            }
        }

        // ─── STATUS CHECK ─────────────────────────────────────────────────────────

        [HttpGet("{id}/payment-status")]
        public async Task<IActionResult> GetRentalStatus(int id)
        {
            var userId = User.FindFirstValue(ClaimTypes.NameIdentifier);
            if (userId == null) return Unauthorized();

            var rental = await _context.Rentals
                .Where(r => r.Id == id && r.UserId == userId)
                .Select(r => new { r.Id, r.Status })
                .FirstOrDefaultAsync();

            if (rental == null) return NotFound();
            
            return Ok(new { status = rental.Status.ToString() });
        }

        // ─── PRIVATE ──────────────────────────────────────────────────────────────

        private bool VerifySepaySignature()
        {
            if (!Request.Headers.TryGetValue("Authorization", out var authHeader))
                return false;

            var expected = "Apikey " + _config["Sepay:WebhookSecret"];
            return authHeader.ToString() == expected;
        }

        private async Task NotifyRentalActivated(Rental rental)
        {
            var vehicleCode = rental.Vehicle?.LicensePlate ?? rental.Vehicle?.Name ?? "Unknown";
            var dockId = "Dock" + rental.StartStationId.ToString();

            await RentalHub.NotifyRentalStatusChanged(
                _rentalHub,
                rental.Id,
                rental.UserId,           // add this
                rental.Status.ToString(),
                vehicleCode,
                dockId);

            await AdminHub.NotifyNewActiveRental(_adminHub, new
            {
                rentalId = rental.Id,
                vehicleCode,
                stationName = rental.StartStation.Name,
                startTime = rental.StartTime
            });

            var availableBikes = await _context.Vehicles
                .CountAsync(v => v.StationId == rental.StartStationId && v.Status == VehicleStatus.Available);

            await AdminHub.NotifyStationUpdate(_adminHub, new
            {
                stationId = rental.StartStationId,
                availableBikes,
                capacity = rental.StartStation.Capacity
            });
        }
    }
}
