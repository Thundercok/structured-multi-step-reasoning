using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;
using SaigonRide.App.Services.Payments;

namespace SaigonRide.App.Services;

public class RideService
{
    public const decimal MinimumStartBalance = 20000m;
    public const decimal MinimumAllowedBalance = -10000m;

    private readonly AppDbContext _db;
    private readonly WalletService _walletService;
    private readonly PaymentStrategyFactory _paymentFactory;

    public RideService(AppDbContext db, WalletService walletService, PaymentStrategyFactory paymentFactory)
    {
        _db = db;
        _walletService = walletService;
        _paymentFactory = paymentFactory;
    }

    public async Task<RideStartResponse> StartRideAsync(string userId, RideStartRequest request,
        CancellationToken cancellationToken = default)
    {
        var rideCard = await _walletService.GetOrCreateRideCardAsync(userId, cancellationToken);
        if (rideCard.Balance < MinimumStartBalance)
            throw new InvalidOperationException("Insufficient Funds");

        var hasActiveRental = await _db.Rentals.AnyAsync(r =>
                r.UserId == userId && (r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending),
            cancellationToken);

        if (hasActiveRental)
            throw new InvalidOperationException("You already have an active rental.");

        var station =
            await _db.Stations.FirstOrDefaultAsync(s => s.Id == request.StationId && s.IsActive, cancellationToken);
        if (station == null)
            throw new InvalidOperationException("Station is not available.");

        var vehicle = await _db.Vehicles.FirstOrDefaultAsync(v => v.Id == request.VehicleId, cancellationToken);
        if (vehicle == null)
            throw new InvalidOperationException("Vehicle not found.");

        if (!vehicle.IsActive || vehicle.Status != VehicleStatus.Available || vehicle.StationId != station.Id)
            throw new InvalidOperationException("Vehicle is not available at this station.");

        await using var transaction = await _db.Database.BeginTransactionAsync(cancellationToken);

        var now = DateTime.UtcNow;
        var rental = new Rental
        {
            UserId = userId,
            VehicleId = vehicle.Id,
            StartStationId = station.Id,
            StartTime = now,
            CreatedAt = now,
            Mode = request.Mode,
            Status = RentalStatus.Active
        };

        vehicle.Status = VehicleStatus.Rented;
        vehicle.StationId = null;

        _db.Rentals.Add(rental);
        await _db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        
        var depositAmount = PricingEngine.CalculateDepositAmount(vehicle.MarketValue, (int)vehicle.Grade);
        var strategy = _paymentFactory.Resolve(request.PaymentMethod ?? "VietQR");
        var paymentResult = await strategy.InitiateAsync(new PaymentContext(
            RentalId: rental.Id,
            Amount: depositAmount,
            UserId: userId,
            BaseUrl: "",
            UserToken: ""
        ));

        return new RideStartResponse
        {
            RentalId = rental.Id,
            VehicleId = vehicle.Id,
            StartStationId = station.Id,
            StartTime = now,
            WalletBalance = rideCard.Balance
            // Map QrUrl and RedirectUrl here if exposed by paymentResult
        };
    }

    public class RideStartResponse
    {
        public int RentalId { get; set; }
        public int VehicleId { get; set; }
        public int StartStationId { get; set; }
        public DateTime StartTime { get; set; }
        public decimal WalletBalance { get; set; }
        public string? QrUrl { get; set; }
        public string? RedirectUrl { get; set; }
    }

    public async Task<RideStopResponse> StopRideAsync(string userId, RideStopRequest request, CancellationToken cancellationToken = default)
    {
        var rental = await _db.Rentals
            .Include(r => r.Vehicle)
            .FirstOrDefaultAsync(r => r.Id == request.RentalId && r.UserId == userId, cancellationToken);

        if (rental == null)
            throw new InvalidOperationException("Rental not found.");

        if (rental.Status != RentalStatus.Active || rental.StartTime == null)
            throw new InvalidOperationException("Rental is not active.");

        var endStation = await _db.Stations.FirstOrDefaultAsync(s => s.Id == request.EndStationId && s.IsActive, cancellationToken);
        if (endStation == null)
            throw new InvalidOperationException("End station is not available.");

        var occupiedDocks = await _db.Vehicles.CountAsync(v => v.StationId == endStation.Id, cancellationToken);
        if (occupiedDocks >= endStation.Capacity)
            throw new InvalidOperationException("End station has no empty docks.");

        var rideCard = await _walletService.GetOrCreateRideCardAsync(userId, cancellationToken);
        var now = DateTime.UtcNow;
        var fare = CalculateFare(rental, now);

        if (rideCard.Balance - fare < MinimumAllowedBalance)
            throw new InvalidOperationException("Insufficient Funds");

        await using var transaction = await _db.Database.BeginTransactionAsync(cancellationToken);

        rental.EndTime = now;
        rental.EndStationId = endStation.Id;
        rental.TotalCost = fare;
        rental.Status = RentalStatus.Completed;

        rental.Vehicle.Status = VehicleStatus.Available;
        rental.Vehicle.StationId = endStation.Id;

        await _walletService.AddCompletedTransactionAsync(
            rideCard,
            -fare,
            RideCardTransactionType.FareDeduction,
            PaymentProvider.Wallet,
            rental.Id,
            $"Fare deduction for rental #{rental.Id}",
            cancellationToken);

        await _db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);

        return new RideStopResponse
        {
            RentalId = rental.Id,
            EndStationId = endStation.Id,
            StartTime = rental.StartTime.Value,
            EndTime = now,
            Fare = fare,
            WalletBalance = rideCard.Balance,
            DurationMinutes = Math.Round((now - rental.StartTime.Value).TotalMinutes, 1)
        };
    }

    private static decimal CalculateFare(Rental rental, DateTime endTime) =>
        rental.Mode == RentalMode.Daily
            ? PricingEngine.CalculateDailyFare(rental.Vehicle.DailyRate, rental.StartTime!.Value, endTime)
            : PricingEngine.CalculateHourlyFare(rental.Vehicle.HourlyRate, rental.StartTime!.Value, endTime);
}