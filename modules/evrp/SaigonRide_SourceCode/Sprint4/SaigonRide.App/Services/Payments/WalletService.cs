using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;
using Stripe;
using Stripe.Checkout;

namespace SaigonRide.App.Services;

public class WalletService
{
    private const decimal MinimumTopUpAmount = 10000m;

    private readonly AppDbContext _db;
    private readonly SepayService _sepayService;

    public WalletService(AppDbContext db, SepayService sepayService)
    {
        _db = db;
        _sepayService = sepayService;
    }

    public async Task<RideCard> GetOrCreateRideCardAsync(string userId, CancellationToken cancellationToken = default)
    {
        var rideCard = await _db.RideCards
            .FirstOrDefaultAsync(c => c.UserId == userId, cancellationToken);

        if (rideCard != null) return rideCard;

        rideCard = new RideCard
        {
            UserId = userId,
            Balance = 0,
            Currency = "VND",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        _db.RideCards.Add(rideCard);
        await _db.SaveChangesAsync(cancellationToken);

        return rideCard;
    }

    public async Task<WalletTopUpResponse> CreateTopUpAsync(string userId, WalletTopUpRequest request, CancellationToken cancellationToken = default)
    {
        if (request.Amount < MinimumTopUpAmount)
            throw new InvalidOperationException($"Minimum top-up amount is {MinimumTopUpAmount:0} VND.");

        if (request.Amount != decimal.Truncate(request.Amount))
            throw new InvalidOperationException("Top-up amount must be a whole VND amount.");

        if (!Enum.TryParse<PaymentProvider>(request.Provider, ignoreCase: true, out var provider) ||
            provider is not (PaymentProvider.Stripe or PaymentProvider.SePay))
        {
            throw new InvalidOperationException("Top-up provider must be Stripe or SePay.");
        }

        var rideCard = await GetOrCreateRideCardAsync(userId, cancellationToken);

        var topUp = new RideCardTransaction
        {
            RideCardId = rideCard.Id,
            Amount = request.Amount,
            BalanceAfter = rideCard.Balance,
            Type = RideCardTransactionType.TopUp,
            Status = RideCardTransactionStatus.Pending,
            Provider = provider,
            Note = "Wallet top-up initiated",
            CreatedAt = DateTime.UtcNow
        };

        _db.RideCardTransactions.Add(topUp);
        await _db.SaveChangesAsync(cancellationToken);

        if (provider == PaymentProvider.SePay)
        {
            var qrUrl = _sepayService.GenerateWalletTopUpQrUrl(request.Amount, topUp.Id);
            topUp.ExternalReference = $"SGRW {topUp.Id}";
            await _db.SaveChangesAsync(cancellationToken);

            return new WalletTopUpResponse
            {
                TransactionId = topUp.Id,
                Amount = topUp.Amount,
                Provider = topUp.Provider.ToString(),
                Status = topUp.Status.ToString(),
                QrUrl = qrUrl,
                TransferContent = topUp.ExternalReference
            };
        }

        var baseUrl = (request.BaseUrl ?? string.Empty).TrimEnd('/');
        if (string.IsNullOrWhiteSpace(baseUrl))
            throw new InvalidOperationException("BaseUrl is required for Stripe checkout.");

        var session = await CreateStripeCheckoutSessionAsync(topUp, userId, baseUrl, cancellationToken);
        topUp.ExternalReference = session.Id;
        await _db.SaveChangesAsync(cancellationToken);

        return new WalletTopUpResponse
        {
            TransactionId = topUp.Id,
            Amount = topUp.Amount,
            Provider = topUp.Provider.ToString(),
            Status = topUp.Status.ToString(),
            CheckoutUrl = session.Url
        };
    }

    public async Task<WalletWebhookResponse> CompleteStripeCheckoutAsync(Session session, CancellationToken cancellationToken = default)
    {
        if (!session.Metadata.TryGetValue("transaction_id", out var transactionIdValue) ||
            !int.TryParse(transactionIdValue, out var transactionId))
        {
            return new WalletWebhookResponse { Success = false, Message = "Stripe session missing wallet transaction metadata." };
        }

        return await CompleteTopUpAsync(
            transactionId,
            PaymentProvider.Stripe,
            session.Id,
            session.AmountTotal.HasValue ? session.AmountTotal.Value : null,
            cancellationToken);
    }

    public async Task<WalletWebhookResponse> CompleteSePayTopUpAsync(SePayWebhookPayload payload, CancellationToken cancellationToken = default)
    {
        if (!string.Equals(payload.transferType, "in", StringComparison.OrdinalIgnoreCase))
            return new WalletWebhookResponse { Success = true, Message = "Ignored outgoing transfer." };

        var match = System.Text.RegularExpressions.Regex.Match(payload.content, @"\bSGRW\s+(\d+)\b", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        if (!match.Success)
            return new WalletWebhookResponse { Success = true, Message = "Ignored transfer without wallet reference." };

        var transactionId = int.Parse(match.Groups[1].Value);
        return await CompleteTopUpAsync(transactionId, PaymentProvider.SePay, payload.referenceCode, payload.transferAmount, cancellationToken);
    }

    public async Task<RideCardTransaction> AddCompletedTransactionAsync(
        RideCard rideCard,
        decimal amount,
        RideCardTransactionType type,
        PaymentProvider provider,
        int? rentalId,
        string? note,
        CancellationToken cancellationToken = default)
    {
        rideCard.Balance += amount;
        rideCard.UpdatedAt = DateTime.UtcNow;

        var walletTransaction = new RideCardTransaction
        {
            RideCardId = rideCard.Id,
            RentalId = rentalId,
            Amount = amount,
            BalanceAfter = rideCard.Balance,
            Type = type,
            Status = RideCardTransactionStatus.Completed,
            Provider = provider,
            Note = note,
            CreatedAt = DateTime.UtcNow,
            ProcessedAt = DateTime.UtcNow
        };

        _db.RideCardTransactions.Add(walletTransaction);
        await _db.SaveChangesAsync(cancellationToken);

        return walletTransaction;
    }

    private async Task<WalletWebhookResponse> CompleteTopUpAsync(
        int transactionId,
        PaymentProvider provider,
        string externalReference,
        decimal? paidAmount,
        CancellationToken cancellationToken)
    {
        await using var dbTransaction = await _db.Database.BeginTransactionAsync(cancellationToken);

        var topUp = await _db.RideCardTransactions
            .Include(t => t.RideCard)
            .FirstOrDefaultAsync(t => t.Id == transactionId && t.Type == RideCardTransactionType.TopUp, cancellationToken);

        if (topUp == null)
            return new WalletWebhookResponse { Success = false, Message = "Wallet transaction not found.", TransactionId = transactionId };

        if (topUp.Provider != provider)
            return new WalletWebhookResponse { Success = false, Message = "Payment provider mismatch.", TransactionId = transactionId };

        if (topUp.Status == RideCardTransactionStatus.Completed)
            return new WalletWebhookResponse { Success = true, Message = "Wallet top-up already completed.", TransactionId = topUp.Id, Balance = topUp.RideCard.Balance };

        if (paidAmount.HasValue && paidAmount.Value < topUp.Amount)
            return new WalletWebhookResponse { Success = false, Message = "Paid amount is below requested top-up amount.", TransactionId = topUp.Id };

        topUp.RideCard.Balance += topUp.Amount;
        topUp.RideCard.UpdatedAt = DateTime.UtcNow;
        topUp.BalanceAfter = topUp.RideCard.Balance;
        topUp.Status = RideCardTransactionStatus.Completed;
        topUp.ExternalReference = externalReference;
        topUp.ProcessedAt = DateTime.UtcNow;
        topUp.Note = "Wallet top-up completed";

        await _db.SaveChangesAsync(cancellationToken);
        await dbTransaction.CommitAsync(cancellationToken);

        return new WalletWebhookResponse
        {
            Success = true,
            Message = "Wallet top-up completed.",
            TransactionId = topUp.Id,
            Balance = topUp.RideCard.Balance
        };
    }

    private async Task<Session> CreateStripeCheckoutSessionAsync(RideCardTransaction topUp, string userId, string baseUrl, CancellationToken cancellationToken)
    {
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
                        Currency = "vnd",
                        UnitAmount = (long)topUp.Amount,
                        ProductData = new SessionLineItemPriceDataProductDataOptions
                        {
                            Name = "SaigonRide RideCard Top-up",
                            Description = $"Wallet transaction #{topUp.Id}"
                        }
                    },
                    Quantity = 1
                }
            ],
            Metadata = new Dictionary<string, string>
            {
                ["purpose"] = "wallet_topup",
                ["transaction_id"] = topUp.Id.ToString(),
                ["user_id"] = userId
            },
            SuccessUrl = $"{baseUrl}/Wallet?topup=success&transaction_id={topUp.Id}",
            CancelUrl = $"{baseUrl}/Wallet?topup=cancelled&transaction_id={topUp.Id}"
        };

        return await new SessionService().CreateAsync(options, cancellationToken: cancellationToken);
    }
}
