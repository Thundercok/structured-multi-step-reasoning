#nullable disable

using System.ComponentModel.DataAnnotations;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.Extensions.Caching.Memory;
using OtpNet;
using SaigonRide.App.Models.Entities;

namespace SaigonRide.Areas.Identity.Pages.Account
{
    public class LoginWith2faModel : PageModel
    {
        private readonly SignInManager<ApplicationUser> _signInManager;
        private readonly UserManager<ApplicationUser>  _userManager;
        private readonly IMemoryCache                  _cache;

        public LoginWith2faModel(
            SignInManager<ApplicationUser> signInManager,
            UserManager<ApplicationUser>   userManager,
            IMemoryCache                   cache)
        {
            _signInManager = signInManager;
            _userManager   = userManager;
            _cache         = cache;
        }

        [BindProperty]
        public InputModel Input { get; set; }

        public string ReturnUrl  { get; set; }
        public bool   RememberMe { get; set; }

        [BindProperty(SupportsGet = true)]
        public string PendingToken { get; set; }

        public class InputModel
        {
            [Required]
            [StringLength(6, MinimumLength = 6)]
            [Display(Name = "Authenticator code")]
            public string TotpCode { get; set; }
        }

        public IActionResult OnGet(string pendingToken, string returnUrl = null, bool rememberMe = false)
        {
            if (!_cache.TryGetValue($"totp_web:{pendingToken}", out string _))
                return RedirectToPage("./Login");

            PendingToken = pendingToken;
            ReturnUrl    = returnUrl ?? Url.Content("~/");
            RememberMe   = rememberMe;
            return Page();
        }

        public async Task<IActionResult> OnPostAsync(string returnUrl = null, bool rememberMe = false)
        {
            returnUrl ??= Url.Content("~/");

            if (!ModelState.IsValid) return Page();

            if (!_cache.TryGetValue($"totp_web:{PendingToken}", out string email))
            {
                ModelState.AddModelError(string.Empty, "Session expired. Please log in again.");
                return RedirectToPage("./Login");
            }

            var user = await _userManager.FindByEmailAsync(email);
            if (user == null) return RedirectToPage("./Login");

            var secretBytes = Base32Encoding.ToBytes(user.TotpSecret);
            var totp        = new Totp(secretBytes);
            var valid       = totp.VerifyTotp(
                Input.TotpCode, out _,
                new VerificationWindow(previous: 1, future: 1));

            if (!valid)
            {
                ModelState.AddModelError(string.Empty, "Invalid authenticator code.");
                return Page();
            }

            _cache.Remove($"totp_web:{PendingToken}");
            await _signInManager.SignInAsync(user, isPersistent: rememberMe);

            var destination = string.IsNullOrEmpty(returnUrl) || returnUrl == "/" ? "/Dashboard" : returnUrl;
            return LocalRedirect(destination);
        }
    }
}