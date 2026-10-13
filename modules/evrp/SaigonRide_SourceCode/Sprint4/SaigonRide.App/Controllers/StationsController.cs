using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;

namespace SaigonRide.App.Controllers;

// --------------------------------------------------------
// 1. MVC CONTROLLER (Handles UI / HTML Views)
// --------------------------------------------------------
[Route("Stations")]
public class StationsController : Controller
{
    private readonly AppDbContext _db;

    public StationsController(AppDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> Index()
    {
        // Using navigation properties instead of sub-queries for cleaner EF translation
        var stations = await _db.Stations
            .Where(s => s.IsActive)
            .Select(s => new StationViewModel
            {
                Id = s.Id,
                Name = s.Name,
                Address = s.Address,
                Capacity = s.Capacity,
                Latitude = s.Latitude,
                Longitude = s.Longitude,
                BikesAvailable = s.Vehicles.Count(v => v.Status == VehicleStatus.Available && v.IsActive)
            })
            .AsNoTracking() // Optimization: Read-only query, no need to track entities
            .ToListAsync();

        return View(stations);
    }
}

// --------------------------------------------------------
// 2. API CONTROLLER (Handles JSON Data / Mobile / SPA)
// --------------------------------------------------------
[ApiController]
[Route("api/[controller]")] // Automatically routes to api/stationsapi
public class StationsApiController : ControllerBase
{
    private readonly AppDbContext _db;

    public StationsApiController(AppDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> GetAll()
    {
        var stations = await _db.Stations
            .Where(s => s.IsActive)
            .Select(s => new 
            {
                s.Id,
                s.Name,
                s.Address,
                s.Latitude,
                s.Longitude,
                s.Capacity,
                BikesAvailable = s.Vehicles.Count(v => v.Status == VehicleStatus.Available && v.IsActive),
                // Calculate utilisation directly in the database projection
                Utilisation = s.Capacity > 0 
                    ? Math.Round((double)s.Vehicles.Count(v => v.Status == VehicleStatus.Available && v.IsActive) / s.Capacity * 100, 0) 
                    : 0.0
            })
            .AsNoTracking()
            .ToListAsync();

        return Ok(stations);
    }

    [HttpGet("{id}/utilisation")]
    public async Task<IActionResult> GetUtilisation(int id)
    {
        var station = await _db.Stations
            .Where(s => s.Id == id && s.IsActive)
            .Select(s => new StationViewModel
            {
                Id = s.Id,
                Name = s.Name,
                Address = s.Address,
                Latitude = s.Latitude,
                Longitude = s.Longitude,
                Capacity = s.Capacity,
                BikesAvailable = s.Vehicles.Count(v => v.Status == VehicleStatus.Available && v.IsActive)
            })
            .AsNoTracking()
            .FirstOrDefaultAsync();

        if (station == null) return NotFound();

        var since = DateTime.UtcNow.AddHours(-24);
        var logs = await _db.StationUtilisationLogs
            .Where(l => l.StationId == id && l.HourSlot >= since)
            .OrderBy(l => l.HourSlot)
            .Select(l => new HourlyLogViewModel
            {
                HourSlot = l.HourSlot,
                BikesAvailable = l.BikesAvailable,
                Capacity = l.Capacity,
                RentalsStarted = l.RentalsStarted,
                RentalsEnded = l.RentalsEnded
            })
            .AsNoTracking()
            .ToListAsync();

        return Ok(new StationUtilisationViewModel { Station = station, HourlyLogs = logs });
    }
}