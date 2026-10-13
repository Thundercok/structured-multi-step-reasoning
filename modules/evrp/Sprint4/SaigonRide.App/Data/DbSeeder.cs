using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Data;

public static class DbSeeder
{
    public static async Task SeedAsync(IServiceProvider services)
    {
        var db          = services.GetRequiredService<AppDbContext>();
        var userManager = services.GetRequiredService<UserManager<ApplicationUser>>();
        var roleManager = services.GetRequiredService<RoleManager<IdentityRole>>();

        // ── 1. Apply Migrations ──────────────────────────────────────────────
        // MUST execute first to ensure tables exist before Identity tries to query/insert.
        await db.Database.MigrateAsync();

        // Pristine Database Reset for UI Test consistency
        db.Rentals.RemoveRange(await db.Rentals.ToListAsync());
        db.Deposits.RemoveRange(await db.Deposits.ToListAsync());
        db.RideCardTransactions.RemoveRange(await db.RideCardTransactions.ToListAsync());
        db.Vehicles.RemoveRange(await db.Vehicles.ToListAsync());
        db.Stations.RemoveRange(await db.Stations.ToListAsync());
        db.RideCards.RemoveRange(await db.RideCards.ToListAsync());
        await db.SaveChangesAsync();

        // ── 2. Roles ─────────────────────────────────────────────────────────
        foreach (var role in new[] { "Admin", "User" })
        {
            if (!await roleManager.RoleExistsAsync(role))
            {
                await roleManager.CreateAsync(new IdentityRole(role));
            }
        }

        // ── 3. Admin user ────────────────────────────────────────────────────
        await EnsureUser(userManager, new ApplicationUser
        {
            UserName       = "admin@saigonride.com",
            Email          = "admin@saigonride.com",
            FullName       = "Admin",
            PhoneNumber    = "0900000000",
            EmailConfirmed = true,
            CreatedAt      = DateTime.UtcNow
        }, "Admin@SaigonRide99!", "Admin");

        // ── 4. Kiosk service account ─────────────────────────────────────────
        await EnsureUser(userManager, new ApplicationUser
        {
            UserName       = "kiosk@saigonride.com",
            Email          = "kiosk@saigonride.com",
            FullName       = "Kiosk",
            PhoneNumber    = "0900000001",
            EmailConfirmed = true,
            CreatedAt      = DateTime.UtcNow
        }, "Kiosk@Internal99!", "User");

        // ── 5. Test user (for Playwright) ────────────────────────────────────
        await EnsureUser(userManager, new ApplicationUser
        {
            UserName       = "test@saigonride.com",
            Email          = "test@saigonride.com",
            FullName       = "Test User",
            PhoneNumber    = "0901234567",
            EmailConfirmed = true,
            CreatedAt      = DateTime.UtcNow
        }, "Test@SaigonRide99!", "User");

        // ── 6. TOTP test user (for Playwright 2FA tests) ─────────────────────
        var totpUser = await userManager.FindByEmailAsync("totp_test@saigonride.com");
        if (totpUser == null)
        {
            totpUser = new ApplicationUser
            {
                UserName       = "totp_test@saigonride.com",
                Email          = "totp_test@saigonride.com",
                FullName       = "TOTP Test User",
                PhoneNumber    = "0909999999",
                EmailConfirmed = true,
                CreatedAt      = DateTime.UtcNow,
                TotpSecret     = "JBSWY3DPEHPK3PXP",
                TotpEnabled    = true
            };
            var result = await userManager.CreateAsync(totpUser, "Test@1234567!");
            if (result.Succeeded) 
            {
                await userManager.AddToRoleAsync(totpUser, "User");
            }
        }
// ── Test user RideCard ────────────────────────────────────────────────────
        var testUser = await userManager.FindByEmailAsync("test@saigonride.com");
        if (testUser != null && !await db.RideCards.AnyAsync(r => r.UserId == testUser.Id))
        {
            db.RideCards.Add(new RideCard
            {
                UserId    = testUser.Id,
                Balance   = 500000,
                Currency  = "VND",
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            });
            await db.SaveChangesAsync();
        }
        // ── 7. Stations ──────────────────────────────────────────────────────
        if (!await db.Stations.AnyAsync())
        {
            var stations = new List<Station>
            {
                new() { Name = "Bến Thành",        Address = "1 Công Trường Quách Thị Trang, Q.1",     Capacity = 20, IsActive = true, Latitude = 10.7721, Longitude = 106.6980 },
                new() { Name = "Nguyễn Huệ",       Address = "Phố đi bộ Nguyễn Huệ, Q.1",              Capacity = 15, IsActive = true, Latitude = 10.7743, Longitude = 106.7030 },
                new() { Name = "Bùi Viện",          Address = "Đường Bùi Viện, Q.1",                    Capacity = 12, IsActive = true, Latitude = 10.7676, Longitude = 106.6920 },
                new() { Name = "Hồ Con Rùa",       Address = "Công viên Hồ Con Rùa, Q.3",              Capacity = 18, IsActive = true, Latitude = 10.7798, Longitude = 106.6967 },
                new() { Name = "Landmark 81",       Address = "720A Điện Biên Phủ, Bình Thạnh",         Capacity = 25, IsActive = true, Latitude = 10.7950, Longitude = 106.7220 },
                new() { Name = "Thảo Cầm Viên",    Address = "2 Nguyễn Bỉnh Khiêm, Q.1",              Capacity = 16, IsActive = true, Latitude = 10.7878, Longitude = 106.7055 },
                new() { Name = "Phố Tây Bùi Viện", Address = "Bùi Viện - Đề Thám, Q.1",               Capacity = 10, IsActive = true, Latitude = 10.7671, Longitude = 106.6912 },
                new() { Name = "Chợ Bến Thành",    Address = "Tứ giác Bến Thành, Q.1",                 Capacity = 20, IsActive = true, Latitude = 10.7726, Longitude = 106.6982 },
            };
            db.Stations.AddRange(stations);
            await db.SaveChangesAsync();
        }

        // ── 8. Vehicles ──────────────────────────────────────────────────────
        if (!await db.Vehicles.AnyAsync())
        {
            var stations = await db.Stations.ToListAsync();
            var vehicles = new List<Vehicle>();

            var specs = new[]
            {
                (Name: "Standard Bike",     Grade: VehicleGrade.GradeC, HourlyRate: 15000m, DailyRate: 80000m,  MarketValue: 3_000_000m),
                (Name: "E-Bike Pro",        Grade: VehicleGrade.GradeC, HourlyRate: 20000m, DailyRate: 100000m, MarketValue: 5_000_000m),
                (Name: "E-Scooter City",    Grade: VehicleGrade.GradeB, HourlyRate: 35000m, DailyRate: 150000m, MarketValue: 12_000_000m),
                (Name: "E-Scooter Sport",   Grade: VehicleGrade.GradeB, HourlyRate: 40000m, DailyRate: 170000m, MarketValue: 15_000_000m),
                (Name: "VinFast Klara S",   Grade: VehicleGrade.GradeA, HourlyRate: 60000m, DailyRate: 250000m, MarketValue: 25_000_000m),
            };

            int plate = 1;
            foreach (var station in stations)
            {
                // 2 vehicles per spec per station → decent fill
                foreach (var spec in specs.Take(3))
                {
                    vehicles.Add(new Vehicle
                    {
                        Name         = spec.Name,
                        LicensePlate = $"SGR-{plate++:D4}",
                        Grade        = spec.Grade,
                        HourlyRate   = spec.HourlyRate,
                        DailyRate    = spec.DailyRate,
                        MarketValue  = spec.MarketValue,
                        Status       = VehicleStatus.Available,
                        IsActive     = true,
                        StationId    = station.Id
                    });
                }
            }
            db.Vehicles.AddRange(vehicles);
            await db.SaveChangesAsync();
        }
    }

    private static async Task EnsureUser(
        UserManager<ApplicationUser> um,
        ApplicationUser user,
        string password,
        string role)
    {
        if (await um.FindByEmailAsync(user.Email!) != null) return;
        var result = await um.CreateAsync(user, password);
        if (result.Succeeded)
        {
            await um.AddToRoleAsync(user, role);
        }

    }
    
}