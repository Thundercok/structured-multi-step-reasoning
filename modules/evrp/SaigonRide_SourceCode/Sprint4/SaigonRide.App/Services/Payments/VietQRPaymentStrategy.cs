namespace SaigonRide.App.Services.Payments;

public class VietQRPaymentStrategy : IPaymentStrategy
{
    private readonly SepayService _sepay;
    public string PaymentMethod => "VietQR";

    public VietQRPaymentStrategy(SepayService sepay) => _sepay = sepay;

    public Task<PaymentResult> InitiateAsync(PaymentContext context)
    {
        var qrUrl = _sepay.GenerateQrUrl(context.Amount, context.RentalId);
        return Task.FromResult(new PaymentResult(Success: true, QrUrl: qrUrl));
    }
}