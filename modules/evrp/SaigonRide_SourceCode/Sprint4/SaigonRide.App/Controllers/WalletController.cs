using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SaigonRide.App.Data;
using SaigonRide.App.Models.ViewModels;
using SaigonRide.App.Services;

namespace SaigonRide.App.Controllers;

[Authorize]
public class WalletController : Controller
{
    private readonly AppDbContext _db;
    private readonly WalletService _walletService;

    public WalletController(AppDbContext db, WalletService walletService)
    {
        _db = db;
        _walletService = walletService;
    }

    [HttpGet]
    public async Task<IActionResult> Index()
    {
        var userId = User.FindFirstValue(ClaimTypes.NameIdentifier)!;
        var rideCard = await _walletService.GetOrCreateRideCardAsync(userId);

        var transactions = await _db.RideCardTransactions
            .Where(t => t.RideCard.UserId == userId)
            .OrderByDescending(t => t.Id)
            .Take(20)
            .ToListAsync();

        ViewBag.Balance      = rideCard.Balance;
        ViewBag.Transactions = transactions;

        var q = Request.Query;
        if (q["topup"] == "success")   ViewBag.Flash = ("success", "Nạp tiền thành công! Số dư đã được cập nhật.");
        else if (q["topup"] == "cancelled") ViewBag.Flash = ("error", "Thanh toán bị hủy.");

        if (TempData["SePayQrUrl"] is string qrUrl)
        {
            ViewBag.SePayQrUrl  = qrUrl;
            ViewBag.SePayAmount = TempData["SePayAmount"];
            ViewBag.SePayRef    = TempData["SePayRef"];
        }

        if (TempData["ErrorMessage"] is string err)
            ViewBag.Flash = ("error", err);

        return View();
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> TopUp([FromForm] decimal amount, [FromForm] string provider)
    {
        var userId  = User.FindFirstValue(ClaimTypes.NameIdentifier)!;
        var baseUrl = $"{Request.Scheme}://{Request.Host}";

        try
        {
            var result = await _walletService.CreateTopUpAsync(userId, new WalletTopUpRequest
            {
                Amount   = amount,
                Provider = provider,
                BaseUrl  = baseUrl
            });

            if (provider.Equals("SePay", StringComparison.OrdinalIgnoreCase))
            {
                TempData["SePayQrUrl"]  = result.QrUrl;
                TempData["SePayAmount"] = amount.ToString("N0");
                TempData["SePayRef"]    = result.TransferContent;
                return RedirectToAction(nameof(Index));
            }

            return Redirect(result.CheckoutUrl!);
        }
        catch (InvalidOperationException ex)
        {
            TempData["ErrorMessage"] = ex.Message;
            return RedirectToAction(nameof(Index));
        }
    }
}