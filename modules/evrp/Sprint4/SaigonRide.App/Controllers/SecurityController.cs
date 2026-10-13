using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using SaigonRide.App.Models.Entities;
[Authorize]
public class SecurityController : Controller
{
    private readonly UserManager<ApplicationUser> _userManager;

    public SecurityController(UserManager<ApplicationUser> userManager)
    {
        _userManager = userManager;
    }

    [HttpGet]
    public async Task<IActionResult> Index()
    {
        var user = await _userManager.GetUserAsync(User);
        if (user == null) return RedirectToAction("Login", "Account", new { area = "Identity" });
        ViewBag.TotpEnabled = user.TotpEnabled;
        return View();
    }

    [HttpGet]
    public async Task<IActionResult> Setup()
    {
        var user = await _userManager.GetUserAsync(User);
        if (user == null) return RedirectToAction("Login", "Account", new { area = "Identity" });
        if (user.TotpEnabled)
            return RedirectToAction(nameof(Index));
        return View();
    }

    [HttpPost]
    public async Task<IActionResult> Disable()
    {
        var user = await _userManager.GetUserAsync(User);
        if (user == null) return Unauthorized();
        user.TotpEnabled  = false;
        user.TotpSecret   = null;
        await _userManager.UpdateAsync(user);
        TempData["Flash"] = "2FA disabled.";
        return RedirectToAction(nameof(Index));
    }
}