namespace SaigonRide.App.Services.Payments;

public interface IPaymentStrategy
{
    string PaymentMethod { get; }
    Task<PaymentResult> InitiateAsync(PaymentContext context);
}

public record PaymentContext(
    int RentalId,
    decimal Amount,
    string UserId,
    string BaseUrl,
    string UserToken
);

public record PaymentResult(
    bool Success,
    string? QrUrl = null,
    string? RedirectUrl = null,
    string? Error = null
);