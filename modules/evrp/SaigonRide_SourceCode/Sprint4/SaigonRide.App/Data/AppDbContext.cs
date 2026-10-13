using Microsoft.AspNetCore.Identity.EntityFrameworkCore;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Data
{
    public class AppDbContext : IdentityDbContext<ApplicationUser>
    {
        public AppDbContext(DbContextOptions<AppDbContext> options) : base(options)
        {
        }

        // Your custom tables
        public DbSet<Vehicle> Vehicles { get; set; }
        public DbSet<Rental> Rentals { get; set; }
        public DbSet<Deposit> Deposits { get; set; }
        
        public DbSet<Station> Stations { get; set; }
        public DbSet<StationUtilisationLog> StationUtilisationLogs { get; set; }
        public DbSet<RideCard> RideCards { get; set; }
        public DbSet<RideCardTransaction> RideCardTransactions { get; set; }
        
        protected override void OnModelCreating(ModelBuilder builder)
        {
            base.OnModelCreating(builder);

            builder.Entity<IdentityUserLogin<string>>()
                .Property(l => l.LoginProvider)
                .HasMaxLength(128);

            builder.Entity<IdentityUserLogin<string>>()
                .Property(l => l.ProviderKey)
                .HasMaxLength(128);

            builder.Entity<IdentityUserToken<string>>()
                .Property(t => t.LoginProvider)
                .HasMaxLength(128);

            builder.Entity<IdentityUserToken<string>>()
                .Property(t => t.Name)
                .HasMaxLength(128);

            builder.Entity<Rental>()
                .HasOne(r => r.Deposit)
                .WithOne(d => d.Rental)
                .HasForeignKey<Deposit>(d => d.RentalId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<Rental>()
                .HasOne(r => r.User)
                .WithMany(u => u.Rentals)
                .HasForeignKey(r => r.UserId)
                .OnDelete(DeleteBehavior.Restrict);

            builder.Entity<RideCard>()
                .HasOne(c => c.User)
                .WithOne(u => u.RideCard)
                .HasForeignKey<RideCard>(c => c.UserId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<RideCard>()
                .HasIndex(c => c.UserId)
                .IsUnique();

            builder.Entity<RideCard>()
                .Property(c => c.Balance)
                .HasPrecision(18, 2);

            builder.Entity<RideCard>()
                .Property(c => c.Currency)
                .HasMaxLength(3);

            builder.Entity<RideCardTransaction>()
                .HasOne(t => t.RideCard)
                .WithMany(c => c.Transactions)
                .HasForeignKey(t => t.RideCardId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<RideCardTransaction>()
                .HasOne(t => t.Rental)
                .WithMany()
                .HasForeignKey(t => t.RentalId)
                .OnDelete(DeleteBehavior.Restrict);

            builder.Entity<RideCardTransaction>()
                .Property(t => t.Amount)
                .HasPrecision(18, 2);

            builder.Entity<RideCardTransaction>()
                .Property(t => t.BalanceAfter)
                .HasPrecision(18, 2);

            builder.Entity<RideCardTransaction>()
                .Property(t => t.ExternalReference)
                .HasMaxLength(128);

            builder.Entity<RideCardTransaction>()
                .HasIndex(t => new { t.Provider, t.ExternalReference });

            builder.Entity<Rental>()
                .HasOne(r => r.Vehicle)
                .WithMany(v => v.Rentals)
                .HasForeignKey(r => r.VehicleId)
                .OnDelete(DeleteBehavior.Restrict);

            builder.Entity<Vehicle>()
                .HasOne(v => v.Station)
                .WithMany(s => s.Vehicles)
                .HasForeignKey(v => v.StationId)
                .OnDelete(DeleteBehavior.SetNull);

            builder.Entity<Rental>()
                .HasOne(r => r.StartStation)
                .WithMany(s => s.StartRentals)
                .HasForeignKey(r => r.StartStationId)
                .OnDelete(DeleteBehavior.Restrict);

            builder.Entity<Rental>()
                .HasOne(r => r.EndStation)
                .WithMany(s => s.EndRentals)
                .HasForeignKey(r => r.EndStationId)
                .OnDelete(DeleteBehavior.Restrict);

            builder.Entity<StationUtilisationLog>()
                .HasOne(l => l.Station)
                .WithMany(s => s.UtilisationLogs)
                .HasForeignKey(l => l.StationId)
                .OnDelete(DeleteBehavior.Cascade);

            builder.Entity<StationUtilisationLog>()
                .HasIndex(l => new { l.StationId, l.HourSlot })
                .IsUnique();
        }
    }
}
