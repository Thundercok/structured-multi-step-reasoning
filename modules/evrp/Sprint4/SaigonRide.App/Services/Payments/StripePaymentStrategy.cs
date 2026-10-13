using Stripe.Checkout;

namespace SaigonRide.App.Services.Payments;

public class StripePaymentStrategy : IPaymentStrategy
{
    public string PaymentMethod => "Stripe";

    public async Task<PaymentResult> InitiateAsync(PaymentContext context)
    {
        var options = new SessionCreateOptions
        {
            PaymentMethodTypes = new List<string> { "card" },
            LineItems = new List<SessionLineItemOptions>
            {
                new()
                {
                    PriceData = new SessionLineItemPriceDataOptions
                    {
                        Currency    = "vnd",
                        UnitAmount  = (long)context.Amount,
                        ProductData = new SessionLineItemPriceDataProductDataOptions
                        {
                            Name = $"SaigonRide Deposit — Rental #{context.RentalId}"
                        }
                    },
                    Quantity = 1
                }
            },
            Mode       = "payment",
            SuccessUrl = $"{context.BaseUrl}/Kiosk?stripe_session={{CHECKOUT_SESSION_ID}}&rental_id={context.RentalId}",
            CancelUrl  = $"{context.BaseUrl}/Kiosk?stripe_cancelled=true&rental_id={context.RentalId}",
            Metadata   = new Dictionary<string, string> { ["rental_id"] = context.RentalId.ToString() }
        };

        var service = new SessionService();
        var session = await service.CreateAsync(options);
        return new PaymentResult(Success: true, RedirectUrl: session.Url);
    }
}