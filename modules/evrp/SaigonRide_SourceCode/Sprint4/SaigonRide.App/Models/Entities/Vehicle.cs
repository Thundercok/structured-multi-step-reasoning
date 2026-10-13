namespace SaigonRide.App.Models.Entities
{
    public class Vehicle
    {
        public int Id { get; set; }
        public string Name { get; set; } = string.Empty; // e.g., "VinFast Klara S"
        public string LicensePlate { get; set; } = string.Empty;
        
        // Tiering for your dynamic deposit logic
        public VehicleGrade Grade { get; set; } // Enum: A, B, C
        public decimal MarketValue { get; set; } // The base for the % deposit
        
        // Pricing Models
        public decimal HourlyRate { get; set; }
        public decimal DailyRate { get; set; }
        
        public bool IsActive { get; set; } = true;
        public VehicleStatus Status { get; set; } = VehicleStatus.Available;
        public int? StationId { get; set; }
        public virtual Station? Station { get; set; }
        public virtual ICollection<Rental> Rentals { get; set; } = new List<Rental>();
    }

    public enum VehicleGrade { GradeA = 2 , GradeB = 1, GradeC = 0 }
    public enum VehicleStatus { Available, Rented, Maintenance, OutOfService }
}