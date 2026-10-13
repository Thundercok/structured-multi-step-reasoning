namespace SaigonRide.App.Models.ViewModels;

public class StationViewModel
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Address { get; set; } = string.Empty;
    public double Latitude { get; set; }
    public double Longitude { get; set; }
    public int Capacity { get; set; }
    public int BikesAvailable { get; set; }
    public double UtilisationRate => Capacity == 0 ? 0 : Math.Round((double)BikesAvailable / Capacity * 100, 1);
}

public class StationUtilisationViewModel
{
    public StationViewModel Station { get; set; } = null!;
    public List<HourlyLogViewModel> HourlyLogs { get; set; } = new();
}

public class HourlyLogViewModel
{
    public DateTime HourSlot { get; set; }
    public int BikesAvailable { get; set; }
    public int Capacity { get; set; }
    public int RentalsStarted { get; set; }
    public int RentalsEnded { get; set; }
    public double UtilisationRate => Capacity == 0 ? 0 : Math.Round((double)BikesAvailable / Capacity * 100, 1);
}