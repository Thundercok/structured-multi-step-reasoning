using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Services;

namespace SaigonRide.App.Controllers;

[Authorize]
public class DashboardController : Controller
{
    private readonly AppDbContext _db;
    private readonly WalletService _walletService;

    public DashboardController(AppDbContext db, WalletService walletService)
    {
        _db = db;
        _walletService = walletService;
    }

    public async Task<IActionResult> Index()
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier)!;

        var rideCard = await _walletService.GetOrCreateRideCardAsync(userId);

        var activeRental = await _db.Rentals
            .Include(r => r.Vehicle)
            .Include(r => r.StartStation)
            .Where(r => r.UserId == userId && r.Status == RentalStatus.Active)
            .FirstOrDefaultAsync();

        var allRentals = await _db.Rentals
            .Include(r => r.Vehicle)
            .Include(r => r.StartStation)
            .Include(r => r.EndStation)
            .Where(r => r.UserId == userId)
            .OrderByDescending(r => r.Id)
            .ToListAsync();

        var recentTransactions = await _db.RideCardTransactions
            .Where(t => t.RideCard.UserId == userId)
            .OrderByDescending(t => t.Id)
            .Take(6)
            .ToListAsync();

        var completedRentals = allRentals.Where(r => r.Status == RentalStatus.Completed).ToList();

        ViewBag.WalletBalance      = rideCard.Balance;
        ViewBag.ActiveRental       = activeRental;
        ViewBag.RecentRentals      = allRentals.Take(8).ToList();
        ViewBag.RecentTransactions = recentTransactions;
        ViewBag.TotalRentals       = allRentals.Count;
        ViewBag.TotalSpent         = completedRentals.Sum(r => r.TotalCost);
        ViewBag.TotalMinutes       = (int)completedRentals
                                        .Where(r => r.StartTime.HasValue && r.EndTime.HasValue)
                                        .Sum(r => (r.EndTime!.Value - r.StartTime!.Value).TotalMinutes);
        ViewBag.FavVehicle         = completedRentals
                                        .GroupBy(r => r.Vehicle?.Name)
                                        .OrderByDescending(g => g.Count())
                                        .Select(g => g.Key)
                                        .FirstOrDefault() ?? "—";

        return View();
    }
}