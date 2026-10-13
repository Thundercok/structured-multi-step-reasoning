using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Controllers;

[Authorize(Roles = "Admin")]
[Route("Admin")]
public class AdminController : Controller
{
    private readonly AppDbContext _db;

    public AdminController(AppDbContext db)
    {
        _db = db;
    }

    [HttpGet]
    public async Task<IActionResult> Index()
    {
        var today = DateTime.UtcNow.Date;

        // 1. Station Metrics
        var stations = await _db.Stations
            .Select(s => new {
                s.Id,
                s.Name,
                s.Capacity,
                AvailableBikes = _db.Vehicles.Count(v => v.StationId == s.Id && v.Status == VehicleStatus.Available)
            }).ToListAsync();

        // 2. Active Rentals
        var activeRentals = await _db.Rentals
            .Include(r => r.User)
            .Include(r => r.Vehicle)
            .Include(r => r.StartStation)
            .Where(r => r.Status == RentalStatus.Active)
            .OrderByDescending(r => r.StartTime)
            .ToListAsync();

        // 3. Financials (Total fare deductions today)
        var dailyRevenue = await _db.RideCardTransactions
            .Where(t => t.CreatedAt >= today && t.Type == RideCardTransactionType.FareDeduction)
            .SumAsync(t => Math.Abs(t.Amount));

        ViewBag.Stations = stations;
        ViewBag.ActiveRentals = activeRentals;
        ViewBag.DailyRevenue = dailyRevenue;

        return View();
    }

    [HttpPost("ForceEndRental/{id}")]
    public async Task<IActionResult> ForceEndRental(int id)
    {
        var rental = await _db.Rentals.FindAsync(id);
        if (rental == null || rental.Status != RentalStatus.Active) return BadRequest("Invalid rental");

        rental.Status = RentalStatus.Completed;
        rental.EndTime = DateTime.UtcNow;
        
        await _db.SaveChangesAsync();
        return Ok(new { message = "Rental force-ended successfully." });
    }

    [HttpPost("ToggleMaintenance/{id}")]
    public async Task<IActionResult> ToggleMaintenance(int id)
    {
        var vehicle = await _db.Vehicles.FindAsync(id);
        if (vehicle == null) return NotFound("Vehicle not found.");

        vehicle.Status = vehicle.Status == VehicleStatus.Available ? VehicleStatus.Maintenance : VehicleStatus.Available;
        await _db.SaveChangesAsync();
        
        return Ok(new { status = vehicle.Status.ToString() });
    }

    [HttpPost("RefundUser")]
    public async Task<IActionResult> RefundUser([FromBody] RefundRequest req)
    {
        var card = await _db.RideCards.FirstOrDefaultAsync(c => c.UserId == req.UserId);
        if (card == null) return BadRequest("User does not have a RideCard.");

        card.Balance += req.Amount;
        
        _db.RideCardTransactions.Add(new RideCardTransaction {
            RideCardId = card.Id,
            Amount = req.Amount,
            BalanceAfter = card.Balance,
            Type = RideCardTransactionType.Refund,
            Status = RideCardTransactionStatus.Completed,
            Provider = PaymentProvider.Admin,
            Note = req.Reason,
            CreatedAt = DateTime.UtcNow,
            ProcessedAt = DateTime.UtcNow
        });

        await _db.SaveChangesAsync();
        return Ok(new { newBalance = card.Balance });
    }
    [HttpGet("UtilisationData")]
    public async Task<IActionResult> UtilisationData()
    {
        var since = DateTime.UtcNow.AddHours(-24);
        var logs = await _db.StationUtilisationLogs
            .Include(l => l.Station)
            .Where(l => l.HourSlot >= since)
            .OrderBy(l => l.HourSlot)
            .Select(l => new {
                station        = l.Station.Name,
                hour           = l.HourSlot.ToString("HH:mm"),
                bikesAvailable = l.BikesAvailable,
                capacity       = l.Capacity,
                utilisation    = l.Capacity > 0
                    ? Math.Round((double)(l.Capacity - l.BikesAvailable) / l.Capacity * 100, 1)
                    : 0.0
            })
            .ToListAsync();

        return Ok(logs);
    }

    [HttpGet("RebalancingRecommendations")]
    public async Task<IActionResult> RebalancingRecommendations()
    {
        var stations = await _db.Stations
            .Select(s => new {
                s.Id, s.Name, s.Capacity,
                Available = _db.Vehicles.Count(v => v.StationId == s.Id && v.Status == VehicleStatus.Available)
            }).ToListAsync();

        var recs = stations.Select(s => new {
            s.Id, s.Name, s.Available, s.Capacity,
            UtilisationPct = s.Capacity > 0
                ? Math.Round((double)(s.Capacity - s.Available) / s.Capacity * 100, 1)
                : 0.0,
            Action   = s.Available == 0            ? "RESTOCK"
                : s.Available == s.Capacity   ? "REDISTRIBUTE"
                : "OK",
            Priority = s.Available == 0                            ? "HIGH"
                : s.Available < (int)(s.Capacity * 0.2)      ? "MEDIUM"
                : "LOW"
        }).OrderByDescending(s => s.UtilisationPct);

        return Ok(recs);
    }
}

public class RefundRequest 
{ 
    public string UserId { get; set; } = string.Empty;
    public decimal Amount { get; set; } 
    public string Reason { get; set; } = string.Empty;
}