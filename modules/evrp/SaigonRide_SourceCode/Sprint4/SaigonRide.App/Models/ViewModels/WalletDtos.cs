using SaigonRide.App.Models.Entities;

namespace SaigonRide.App.Models.ViewModels;

public class WalletBalanceResponse
{
    public decimal Balance { get; set; }
    public string Currency { get; set; } = "VND";
}

public class WalletTopUpRequest
{
    public decimal Amount { get; set; }
    public string Provider { get; set; } = string.Empty;
    public string? BaseUrl { get; set; }
}

public class WalletTopUpResponse
{
    public int TransactionId { get; set; }
    public decimal Amount { get; set; }
    public string Provider { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string? CheckoutUrl { get; set; }
    public string? QrUrl { get; set; }
    public string? TransferContent { get; set; }
}

public class WalletWebhookResponse
{
    public bool Success { get; set; }
    public string Message { get; set; } = string.Empty;
    public int? TransactionId { get; set; }
    public decimal? Balance { get; set; }
}
