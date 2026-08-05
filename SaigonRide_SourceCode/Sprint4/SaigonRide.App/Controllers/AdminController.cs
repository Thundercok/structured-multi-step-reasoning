using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.SignalR;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Services;
using SaigonRide.App.Hubs;

namespace SaigonRide.App.Controllers;

[Authorize(Roles = "Admin")]
[Route("Admin")]
public class AdminController : Controller
{
    private readonly AppDbContext _db;
    private readonly EvrpSolverService _evrpSolver;
    private readonly IHubContext<AdminHub> _adminHub;

    public AdminController(AppDbContext db, EvrpSolverService evrpSolver, IHubContext<AdminHub> adminHub)
    {
        _db = db;
        _evrpSolver = evrpSolver;
        _adminHub = adminHub;
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

    [HttpGet("SolveEvrp")]
    public async Task<IActionResult> SolveEvrp()
    {
        var stations = await _db.Stations.Where(s => s.IsActive).ToListAsync();
        
        var availableMap = await _db.Vehicles
            .Where(v => v.Status == VehicleStatus.Available && v.IsActive && v.StationId != null)
            .GroupBy(v => v.StationId!.Value)
            .Select(g => new { StationId = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.StationId, x => x.Count);

        int depotId = stations.FirstOrDefault()?.Id ?? 1;

        var solution = _evrpSolver.Solve(stations, availableMap, depotId);
        return Ok(solution);
    }

    [HttpPost("ExecuteEvrp")]
    public async Task<IActionResult> ExecuteEvrp()
    {
        var stations = await _db.Stations.Where(s => s.IsActive).ToListAsync();
        var allVehicles = await _db.Vehicles
            .Where(v => v.Status == VehicleStatus.Available && v.IsActive && v.StationId != null)
            .ToListAsync();

        var surplusVehicles = new List<Vehicle>();
        var deficits = new List<(int StationId, int DeficitCount)>();

        foreach (var station in stations)
        {
            var stationVehicles = allVehicles.Where(v => v.StationId == station.Id).ToList();
            int target = station.Capacity / 2;
            int surplus = stationVehicles.Count - target;
            if (surplus > 0)
            {
                surplusVehicles.AddRange(stationVehicles.Take(surplus));
            }
            else if (surplus < 0)
            {
                deficits.Add((station.Id, -surplus));
            }
        }

        int moved = 0;
        int surplusPointer = 0;

        foreach (var deficit in deficits)
        {
            int needed = deficit.DeficitCount;
            while (needed > 0 && surplusPointer < surplusVehicles.Count)
            {
                var vehicle = surplusVehicles[surplusPointer++];
                vehicle.StationId = deficit.StationId;
                needed--;
                moved++;
            }
        }

        if (moved > 0)
        {
            await _db.SaveChangesAsync();

            // Notify clients of the station updates in real-time
            foreach (var station in stations)
            {
                var availCount = allVehicles.Count(v => v.StationId == station.Id);
                await AdminHub.NotifyStationUpdate(_adminHub, new {
                    StationId = station.Id,
                    AvailableBikes = availCount,
                    Capacity = station.Capacity
                });
            }
        }

        return Ok(new { success = true, movedCount = moved });
    }
}

public class RefundRequest 
{ 
    public string UserId { get; set; } = string.Empty;
    public decimal Amount { get; set; } 
    public string Reason { get; set; } = string.Empty;
}