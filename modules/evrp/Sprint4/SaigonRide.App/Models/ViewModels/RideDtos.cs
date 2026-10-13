using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Models.ViewModels;

public class RideStartRequest
{
    public int StationId { get; set; }
    public int VehicleId { get; set; }
    public RentalMode Mode { get; set; } = RentalMode.Hourly;
    public string? PaymentMethod { get; set; }
}

public class RideStartResponse
{
    public int RentalId { get; set; }
    public int VehicleId { get; set; }
    public int StartStationId { get; set; }
    public DateTime StartTime { get; set; }
    public decimal WalletBalance { get; set; }
}

public class RideStopRequest
{
    public int RentalId { get; set; }
    public int EndStationId { get; set; }
}

public class RideStopResponse
{
    public int RentalId { get; set; }
    public int EndStationId { get; set; }
    public DateTime StartTime { get; set; }
    public DateTime EndTime { get; set; }
    public decimal Fare { get; set; }
    public decimal WalletBalance { get; set; }
    public double DurationMinutes { get; set; }
}
