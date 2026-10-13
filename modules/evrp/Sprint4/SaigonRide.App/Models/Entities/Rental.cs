namespace SaigonRide.App.Models.Entities
{
    public class Rental
    {
        public int Id { get; set; }

        public string UserId { get; set; } = string.Empty;
        public virtual ApplicationUser User { get; set; } = null!;

        public int VehicleId { get; set; }
        public virtual Vehicle Vehicle { get; set; } = null!;
        
        public int StartStationId { get; set; }
        public virtual Station StartStation { get; set; } = null!;
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public int? EndStationId { get; set; }
        public virtual Station? EndStation { get; set; }
        // Thay đổi: Cho phép null để hỗ trợ trạng thái Pending
        public DateTime? StartTime { get; set; } 
        public DateTime? EndTime { get; set; }

        public RentalMode Mode { get; set; }
        public decimal TotalCost { get; set; }

        public RentalStatus Status { get; set; } = RentalStatus.Pending;

        public virtual Deposit? Deposit { get; set; }
    }

    public enum RentalMode { Hourly, Daily }
    public enum RentalStatus { Pending, Active, Completed, Cancelled }
}