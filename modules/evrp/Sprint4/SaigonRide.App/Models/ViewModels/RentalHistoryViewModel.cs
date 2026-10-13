namespace SaigonRide.App.Models.ViewModels
{
    public class RentalHistoryViewModel
    {
        public int RentalId { get; set; }
        public string VehicleName { get; set; } = string.Empty;
        public string StartTime { get; set; } = string.Empty;
        public string? EndTime { get; set; }
        public string Status { get; set; } = string.Empty;
        public decimal TotalCost { get; set; }
        public decimal DepositAmount { get; set; }
    }
}