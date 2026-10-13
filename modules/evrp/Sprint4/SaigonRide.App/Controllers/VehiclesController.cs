using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Controllers;

[Route("api/[controller]")]
[ApiController]
[Authorize(AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme)]
public class VehiclesController : ControllerBase
{
    private readonly AppDbContext _db;
    public VehiclesController(AppDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> GetAvailable([FromQuery] int? stationId)
    {
        var query = _db.Vehicles
            .Where(v => v.IsActive && v.Status == VehicleStatus.Available);

        if (stationId.HasValue)
            query = query.Where(v => v.StationId == stationId);

        // Also exclude vehicles with active/pending rentals (race condition guard)
        var occupiedIds = await _db.Rentals
            .Where(r => r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending)
            .Select(r => r.VehicleId)
            .ToListAsync();

        query = query.Where(v => !occupiedIds.Contains(v.Id));

        var vehicles = await query
            .OrderBy(v => v.Grade)
            .Select(v => new
            {
                id           = v.Id,
                name         = v.Name,
                licensePlate = v.LicensePlate,
                grade        = (int)v.Grade,   // GradeC=0, GradeB=1, GradeA=2
                hourlyRate   = v.HourlyRate,
                dailyRate    = v.DailyRate,
                marketValue  = v.MarketValue,
                stationId    = v.StationId
            })
            .ToListAsync();

        return Ok(vehicles);
    }

    [HttpGet("{id}")]
    public async Task<IActionResult> GetById(int id)
    {
        var v = await _db.Vehicles.FindAsync(id);
        if (v == null) return NotFound();
        return Ok(new {
            id           = v.Id,
            name         = v.Name,
            licensePlate = v.LicensePlate,
            grade        = (int)v.Grade,
            hourlyRate   = v.HourlyRate,
            dailyRate    = v.DailyRate,
            marketValue  = v.MarketValue,
            status       = v.Status.ToString()
        });
    }

    [HttpPost("{id}/toggle-maintenance")]
    [Authorize(Roles = "Admin")]
    public async Task<IActionResult> ToggleMaintenance(int id)
    {
        var vehicle = await _db.Vehicles.FindAsync(id);
        if (vehicle == null) return NotFound();
        vehicle.Status = vehicle.Status == VehicleStatus.Available
            ? VehicleStatus.Maintenance
            : VehicleStatus.Available;
        await _db.SaveChangesAsync();
        return Ok(new { status = vehicle.Status.ToString() });
    }
}