namespace SaigonRide.App.Services.Payments;

public class PaymentStrategyFactory
{
    private readonly IEnumerable<IPaymentStrategy> _strategies;

    public PaymentStrategyFactory(IEnumerable<IPaymentStrategy> strategies)
        => _strategies = strategies;

    public IPaymentStrategy Resolve(string paymentMethod) =>
        _strategies.FirstOrDefault(s => s.PaymentMethod == paymentMethod)
        ?? throw new InvalidOperationException($"No strategy for payment method: {paymentMethod}");
}