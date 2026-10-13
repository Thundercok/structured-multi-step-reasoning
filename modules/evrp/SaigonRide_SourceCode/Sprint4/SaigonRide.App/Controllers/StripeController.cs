using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Settings;
using Stripe;
using Stripe.Checkout;

namespace SaigonRide.App.Controllers;

[ApiController]
[Route("api/payment/stripe")]
public class StripeController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly StripeSettings _stripe;
    private readonly ILogger<StripeController> _logger;

    public StripeController(AppDbContext db, IOptions<StripeSettings> stripe, ILogger<StripeController> logger)
    {
        _db     = db;
        _stripe = stripe.Value;
        _logger = logger;
    }

    [HttpPost("create-checkout")]
    [Authorize(AuthenticationSchemes = JwtBearerDefaults.AuthenticationScheme)]
    public async Task<IActionResult> CreateCheckout([FromBody] CreateCheckoutRequest req)
    {
        var rental = await _db.Rentals.FindAsync(req.RentalId);
        if (rental == null || rental.Status != RentalStatus.Pending)
            return BadRequest(new { error = "Invalid or non-pending rental." });

        var options = new SessionCreateOptions
        {
            PaymentMethodTypes = ["card"],
            Mode = "payment",
            LineItems =
            [
                new SessionLineItemOptions
                {
                    PriceData = new SessionLineItemPriceDataOptions
                    {
                        Currency  = "vnd",           // zero-decimal — raw VND, NOT ×100
                        UnitAmount = req.DepositAmountVnd,
                        ProductData = new SessionLineItemPriceDataProductDataOptions
                        {
                            Name        = "SaigonRide Deposit",
                            Description = $"Rental #{rental.Id}"
                        }
                    },
                    Quantity = 1
                }
            ],
            Metadata = new Dictionary<string, string>
            {
                { "rental_id", rental.Id.ToString() }
            },
            SuccessUrl = $"{req.BaseUrl}/Kiosk?stripe_session={{CHECKOUT_SESSION_ID}}&rental_id={rental.Id}",
            CancelUrl  = $"{req.BaseUrl}/Kiosk?stripe_cancelled=true&rental_id={rental.Id}",
        };

        var session = await new SessionService().CreateAsync(options);
        _logger.LogInformation("Stripe session {SessionId} created for rental {RentalId}", session.Id, rental.Id);
        return Ok(new { url = session.Url });
    }

    [HttpPost("webhook")]
    [AllowAnonymous]
    public async Task<IActionResult> Webhook()
    {
        var json = await new StreamReader(Request.Body).ReadToEndAsync();

        try
        {
            var stripeEvent = EventUtility.ConstructEvent(
                json,
                Request.Headers["Stripe-Signature"],
                _stripe.WebhookSecret
            );

            if (stripeEvent.Type == Events.CheckoutSessionCompleted)            {
                var session = (Session)stripeEvent.Data.Object;

                if (session.Metadata.TryGetValue("rental_id", out var rentalIdStr)
                    && int.TryParse(rentalIdStr, out var rentalId))
                {
                    var rental = await _db.Rentals.FindAsync(rentalId);
                    if (rental != null && rental.Status == RentalStatus.Pending)
                    {
                        rental.Status    = RentalStatus.Active;
                        rental.StartTime = DateTime.UtcNow;
                        await _db.SaveChangesAsync();
                        _logger.LogInformation("Stripe activated rental {RentalId}", rentalId);
                    }
                }
            }

            return Ok();
        }
        catch (StripeException ex)
        {
            _logger.LogWarning("Stripe webhook signature invalid: {Message}", ex.Message);
            return BadRequest();
        }
    }
}

public record CreateCheckoutRequest(int RentalId, long DepositAmountVnd, string BaseUrl);
