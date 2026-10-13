namespace SaigonRide.App.Models.Entities;

public class RideCard
{
    public int Id { get; set; }

    public string UserId { get; set; } = string.Empty;
    public virtual ApplicationUser User { get; set; } = null!;

    public decimal Balance { get; set; }
    public string Currency { get; set; } = "VND";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    public virtual ICollection<RideCardTransaction> Transactions { get; set; } = new List<RideCardTransaction>();
}

