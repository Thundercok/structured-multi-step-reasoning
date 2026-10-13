using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Models.ViewModels
{
    public class RentalRequest
    {
        public int VehicleId { get; set; }
        public RentalMode Mode { get; set; } // 0 for Hourly, 1 for Daily
    }
}