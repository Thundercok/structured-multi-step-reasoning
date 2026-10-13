namespace SaigonRide.App.Models.Entities
{
    public class RideCardTransaction
    {
        public int Id { get; set; }

        public int RideCardId { get; set; }
        public virtual RideCard RideCard { get; set; } = null!;

        public int? RentalId { get; set; }
        public virtual Rental? Rental { get; set; }

        public decimal Amount { get; set; }
        public decimal BalanceAfter { get; set; }
        public RideCardTransactionType Type { get; set; }
        public RideCardTransactionStatus Status { get; set; } = RideCardTransactionStatus.Pending;
        public PaymentProvider Provider { get; set; } = PaymentProvider.Wallet;
        public string? ExternalReference { get; set; }
        public string? Note { get; set; }
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime? ProcessedAt { get; set; }
    }


    public enum RideCardTransactionType
    {
        TopUp,
        FareDeduction,
        Refund,
        Adjustment
    }

    public enum RideCardTransactionStatus
    {
        Pending,
        Completed,
        Failed,
        Cancelled
    }

    public enum PaymentProvider
    {
        Wallet,
        Stripe,
        SePay,
        Admin
    }
}
