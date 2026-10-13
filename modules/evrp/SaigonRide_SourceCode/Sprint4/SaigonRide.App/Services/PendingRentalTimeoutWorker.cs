using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Services
{
    public class PendingRentalTimeoutWorker : BackgroundService
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<PendingRentalTimeoutWorker> _logger;
        private readonly TimeSpan _interval = TimeSpan.FromMinutes(1);
        private readonly TimeSpan _timeout = TimeSpan.FromMinutes(15);

        public PendingRentalTimeoutWorker(IServiceScopeFactory scopeFactory, ILogger<PendingRentalTimeoutWorker> logger)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                try
                {
                    await CancelExpiredRentalsAsync();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "PendingRentalTimeoutWorker error — will retry next interval.");
                }
                await Task.Delay(_interval, stoppingToken);
            }
        }
        private async Task CancelExpiredRentalsAsync()
        {
            using var scope = _scopeFactory.CreateScope();
            var context = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            var cutoff = DateTime.UtcNow - _timeout;
            var expired = await context.Rentals
                .Include(r => r.Deposit)
                .Where(r => r.Status == RentalStatus.Pending && r.CreatedAt < cutoff)
                .ToListAsync();

            if (!expired.Any()) return;

            foreach (var rental in expired)
            {
                rental.Status = RentalStatus.Cancelled;
                if (rental.Deposit != null)
                {
                    rental.Deposit.Status = DepositStatus.Cancelled;
                    rental.Deposit.ProcessedAt = DateTime.UtcNow;
                    rental.Deposit.Note = "Auto-cancelled: payment timeout";
                }
            }

            await context.SaveChangesAsync();
            _logger.LogInformation("Cancelled {Count} expired pending rentals.", expired.Count);
        }
    }
}