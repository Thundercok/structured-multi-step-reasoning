namespace SaigonRide.App.Models.ViewModels
{
    public class FleetStatusViewModel
    {
        public int TotalVehicles { get; set; }
        public int CurrentlyRented { get; set; }
        public int Available { get; set; }
        public decimal TotalDepositsHeld { get; set; }
        public List<VehicleLocationSummary> VehicleDetails { get; set; } = new();
    }

    public class VehicleLocationSummary
    {
        public string Name { get; set; } = string.Empty;
        public string Plate { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
        public string? CurrentUser { get; set; }
    }
}