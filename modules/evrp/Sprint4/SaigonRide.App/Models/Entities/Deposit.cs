namespace SaigonRide.App.Models.Entities
{
    public class Deposit
    {
        public int Id { get; set; }

        // Strict 1-to-1 link to the Rental transaction
        public int RentalId { get; set; }
        public virtual Rental Rental { get; set; } = null!;

        // The calculated percentage-based amount
        public decimal Amount { get; set; }
        
        // Lifecycle of the deposit
        public DepositStatus Status { get; set; } = DepositStatus.Pending;
        // Audit trail for examiners/admin dashboard
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime? ProcessedAt { get; set; } // When it was refunded or forfeited
        // Optional: Admin notes if a deposit is forfeited (e.g., "Scratched mirror")
        public string? Note { get; set; }
    }

    public enum DepositStatus { Pending, Held, Refunded, Forfeited, Cancelled }
}