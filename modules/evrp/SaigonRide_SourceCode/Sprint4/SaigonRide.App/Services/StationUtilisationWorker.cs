using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;

public class StationUtilisationWorker : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<StationUtilisationWorker> _logger;

    public StationUtilisationWorker(IServiceScopeFactory scopeFactory, ILogger<StationUtilisationWorker> logger)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            var now = DateTime.UtcNow;
            var nextHour = now.AddHours(1).Date.AddHours(now.AddHours(1).Hour);
            var delay = nextHour - now;

            await Task.Delay(delay, stoppingToken);

            try
            {
                await LogSnapshotAsync(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "StationUtilisationWorker failed during snapshot.");
            }
        }
    }

    private async Task LogSnapshotAsync(CancellationToken stoppingToken)
    {
        using var scope = _scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        
        

        var hourSlot = DateTime.UtcNow;
        hourSlot = new DateTime(hourSlot.Year, hourSlot.Month, hourSlot.Day, hourSlot.Hour, 0, 0, DateTimeKind.Utc);

        var stations = await db.Stations
            .Where(s => s.IsActive)
            .Include(s => s.Vehicles)
            .ToListAsync(stoppingToken);

        foreach (var station in stations)
        {
            var bikesAvailable = station.Vehicles.Count(v => v.Status == VehicleStatus.Available);

            var rentalsStarted = await db.Rentals
                .CountAsync(r => r.StartStationId == station.Id &&
                                 r.StartTime >= hourSlot.AddHours(-1) &&
                                 r.StartTime < hourSlot, stoppingToken);

            var rentalsEnded = await db.Rentals
                .CountAsync(r => r.EndStationId == station.Id &&
                                 r.EndTime >= hourSlot.AddHours(-1) &&
                                 r.EndTime < hourSlot, stoppingToken);

            var existing = await db.StationUtilisationLogs
                .FirstOrDefaultAsync(l => l.StationId == station.Id && l.HourSlot == hourSlot, stoppingToken);

            if (existing != null) continue; // unique constraint guard

            db.StationUtilisationLogs.Add(new StationUtilisationLog
            {
                StationId = station.Id,
                HourSlot = hourSlot,
                BikesAvailable = bikesAvailable,
                Capacity = station.Capacity,
                RentalsStarted = rentalsStarted,
                RentalsEnded = rentalsEnded
            });
        }

        await db.SaveChangesAsync(stoppingToken);
        _logger.LogInformation("Station utilisation snapshot logged for {HourSlot}", hourSlot);
    }
}