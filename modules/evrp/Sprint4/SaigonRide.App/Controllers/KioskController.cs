using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;

namespace SaigonRide.App.Controllers;

public class KioskController : Controller
{
    private readonly AppDbContext _db;
    private readonly IConfiguration _config;

    public KioskController(AppDbContext db, IConfiguration config)
    {
        _db     = db;
        _config = config;
    }

    public async Task<IActionResult> Index()
    {
        var stationId = _config.GetValue<int>("Kiosk:StationId");
        var station   = await _db.Stations.FindAsync(stationId);

        if (station == null)
        {
            // Fallback: first active station in DB — prevents crash on misconfigured kiosk
            station = await _db.Stations.FirstOrDefaultAsync(s => s.IsActive);
        }

        if (station == null)
        {
            return Content("No active stations found. Please seed the database.");
        }

        return View(station);
    }
}