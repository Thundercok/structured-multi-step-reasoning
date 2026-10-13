namespace SaigonRide.App.Models.ViewModels;

public class ActiveRentalViewModel
{
    public int RentalId { get; set; }
    public string VehicleName { get; set; } = string.Empty;
    public string LicensePlate { get; set; } = string.Empty;
    public string StartStationName { get; set; } = string.Empty;
    public double StartStationLat { get; set; }
    public double StartStationLng { get; set; }
    public DateTime StartTime { get; set; }
    public string ElapsedTime { get; set; } = string.Empty;
    public decimal HourlyRate { get; set; }
}