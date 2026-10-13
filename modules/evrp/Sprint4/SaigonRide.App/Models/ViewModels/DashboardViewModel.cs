namespace SaigonRide.App.Models.ViewModels;

public class DashboardViewModel
{
    public string UserName { get; set; } = string.Empty;
    public ActiveRentalViewModel? ActiveRental { get; set; }
    public List<RentalHistoryViewModel> History { get; set; } = new();
    public List<SaigonRide.App.Models.Entities.Station> Stations { get; set; } = new();
}