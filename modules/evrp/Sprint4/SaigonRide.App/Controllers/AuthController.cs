using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using SaigonRide.App.Models.Entities;
using SaigonRide.App.Models.ViewModels;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using System.Text;
using Microsoft.IdentityModel.Tokens;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.EntityFrameworkCore;
using OtpNet;
using QRCoder;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using SaigonRide.App.Data;

namespace SaigonRide.App.Controllers
{
    
    [Route("api/[controller]")]
    [ApiController]
    public class AuthController : ControllerBase
    {
        private readonly SignInManager<ApplicationUser> _signInManager;
        private readonly UserManager<ApplicationUser> _userManager;
        private readonly IConfiguration _config;
        private readonly IMemoryCache _cache;
        private readonly IWebHostEnvironment _env;

        public AuthController(
            SignInManager<ApplicationUser> signInManager,
            UserManager<ApplicationUser> userManager,
            IConfiguration config,
            IMemoryCache cache,
            IWebHostEnvironment env)
        {
            _signInManager = signInManager;
            _userManager   = userManager;
            _config        = config;
            _cache         = cache;
            _env           = env;
        }

        [HttpPost("register")]
        public async Task<IActionResult> Register([FromBody] RegisterRequest request)
        {
            var user = new ApplicationUser
            {
                UserName  = request.Email,
                Email     = request.Email,
                FullName  = request.FullName,
                CreatedAt = DateTime.UtcNow
            };

            var result = await _userManager.CreateAsync(user, request.Password);
            if (!result.Succeeded)
                return BadRequest(new { Errors = result.Errors.Select(e => e.Description) });

            return Ok(new { Message = "Registered successfully.", UserId = user.Id });
        }

        [HttpPost("login")]
        public async Task<IActionResult> Login([FromBody] LoginRequest request)
        {
            var user = await _userManager.FindByEmailAsync(request.Email);
            if (user == null)
                return Unauthorized(new { Message = "Invalid email or password." });

            var result = await _signInManager.CheckPasswordSignInAsync(user, request.Password, lockoutOnFailure: false);
            if (!result.Succeeded)
                return Unauthorized(new { Message = "Invalid email or password." });

            if (user.TotpEnabled)
            {
                var pendingToken = Guid.NewGuid().ToString("N");
                _cache.Set($"totp_pending:{pendingToken}", user.Id, TimeSpan.FromMinutes(5));
                return Ok(new { requiresTotp = true, pendingToken });
            }

            return Ok(new
            {
                Token    = GenerateJwt(user, hours: 1),
                UserId   = user.Id,
                FullName = user.FullName
            });
        }

        [HttpPost("kiosk-token")]
        [AllowAnonymous]
        public async Task<IActionResult> KioskToken()
        {
            var email    = _config["KioskCredentials:Email"];
            var password = _config["KioskCredentials:Password"];
            if (_env.IsDevelopment())
            {
                email    ??= "kiosk@saigonride.com";
                password ??= "Kiosk@Internal99!";
            }

            if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password))
                return Unauthorized();

            var user = await _userManager.FindByEmailAsync(email);
            if (user == null) return Unauthorized();

            var result = await _signInManager.CheckPasswordSignInAsync(user, password, lockoutOnFailure: false);
            if (!result.Succeeded) return Unauthorized();

            return Ok(new { token = GenerateJwt(user, hours: 8) });
        }

[HttpPost("send-otp")]
[AllowAnonymous]
public async Task<IActionResult> SendOtp([FromBody] SendOtpRequest request)
{
    var user = await _userManager.FindByEmailAsync(request.Email);
    if (user == null)
        return NotFound(new { message = "Email chưa được đăng ký." });

    var otp = new Random().Next(100000, 999999).ToString();
    _cache.Set($"otp:{request.Email}", otp, TimeSpan.FromMinutes(5));
    Console.WriteLine($"[OTP] {request.Email} → {otp}");

    var apiKey = _config["Resend:ApiKey"];
    if (!string.IsNullOrWhiteSpace(apiKey))
    {
        using var http = new HttpClient();
        http.DefaultRequestHeaders.Authorization =
            new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", apiKey);

        await http.PostAsJsonAsync("https://api.resend.com/emails", new
        {
            from    = _config["Resend:From"] ?? "SaigonRide <onboarding@resend.dev>",
            to      = new[] { request.Email },
            subject = "Mã OTP SaigonRide",
            html    = $@"<div style='font-family:sans-serif;max-width:400px'>
                           <h2>SaigonRide</h2>
                           <p>Mã OTP của bạn:</p>
                           <h1 style='letter-spacing:8px;color:#2A5C43'>{otp}</h1>
                           <p style='color:#999'>Hiệu lực trong 5 phút.</p>
                         </div>"
        });
    }

    return Ok(new { message = "OTP đã được gửi." });
}


[HttpPost("verify-otp")]
[AllowAnonymous]
public async Task<IActionResult> VerifyOtp([FromBody] VerifyOtpRequest request)
{
    bool otpValid = false;

    var bypassOtp = _config["TestSettings:OtpBypass"];
    if (!string.IsNullOrEmpty(bypassOtp) && request.Otp == bypassOtp)
        otpValid = true;
    else if (_env.IsDevelopment() && request.Otp == "123456")
        otpValid = true;
    else if (_cache.TryGetValue($"otp:{request.Email}", out string? stored) && stored == request.Otp)
    {
        otpValid = true;
        _cache.Remove($"otp:{request.Email}");
    }

    if (!otpValid)
        return Unauthorized(new { message = "Mã OTP không đúng hoặc đã hết hạn." });

    var user = await _userManager.FindByEmailAsync(request.Email);
    if (user == null) return Unauthorized();

// Remove the TotpEnabled block entirely
    return Ok(new { token = GenerateJwt(user, hours: 2), userName = user.FullName });
}
[HttpPost("totp/setup")]
[Authorize]
public async Task<IActionResult> TotpSetup()
{
    var user = await _userManager.GetUserAsync(User);
    if (user == null) return Unauthorized();

    // Generate new secret every time setup is called (re-enrollment)
    var secret = Base32Encoding.ToString(OtpNet.KeyGeneration.GenerateRandomKey(20));
    
    user.TotpSecret = secret;
    await _userManager.UpdateAsync(user);

    var issuer  = "SaigonRide";
    var account = user.Email ?? user.UserName ?? "user";
    var uri     = $"otpauth://totp/{Uri.EscapeDataString(issuer)}:{Uri.EscapeDataString(account)}?secret={secret}&issuer={Uri.EscapeDataString(issuer)}&algorithm=SHA1&digits=6&period=30";

    using var qrGenerator  = new QRCodeGenerator();
    using var qrData       = qrGenerator.CreateQrCode(uri, QRCodeGenerator.ECCLevel.Q);
    using var qrCode = new PngByteQRCode(qrData);
    var pngBytes     = qrCode.GetGraphic(5);
    var base64       = Convert.ToBase64String(pngBytes);
    return Ok(new { qrDataUrl = $"data:image/png;base64,{base64}", secret });
}

[HttpPost("totp/enable")]
[Authorize]
public async Task<IActionResult> TotpEnable([FromBody] TotpEnableRequest request)
{
    var user = await _userManager.GetUserAsync(User);
    if (user == null) return Unauthorized();
    if (string.IsNullOrEmpty(user.TotpSecret))
        return BadRequest(new { message = "Run setup first." });

    if (!VerifyTotpCode(user.TotpSecret, request.Code))
        return BadRequest(new { message = "Invalid code." });

    user.TotpEnabled = true;
    await _userManager.UpdateAsync(user);
    return Ok(new { message = "TOTP enabled." });
}

[HttpPost("totp/verify")]
[AllowAnonymous]
public async Task<IActionResult> TotpVerify([FromBody] TotpVerifyRequest request)
{
    if (!_cache.TryGetValue($"totp_pending:{request.PendingToken}", out string? userId))
        return Unauthorized(new { message = "Invalid or expired session." });

    var user = await _userManager.FindByIdAsync(userId!);
    if (user == null) return Unauthorized();

    if (!VerifyTotpCode(user.TotpSecret!, request.Code))
        return Unauthorized(new { message = "Invalid TOTP code." });

    _cache.Remove($"totp_pending:{request.PendingToken}");
    return Ok(new { token = GenerateJwt(user, hours: 2), userName = user.FullName });
}

private bool VerifyTotpCode(string secret, string code)
{
    var secretBytes = Base32Encoding.ToBytes(secret);
    var totp        = new OtpNet.Totp(secretBytes);
    return totp.VerifyTotp(code, out _, new OtpNet.VerificationWindow(previous: 1, future: 1));
}
        // ── Shared JWT factory ────────────────────────────────────────────────
        private string GenerateJwt(ApplicationUser user, int hours)
        {
            var jwtSettings = _config.GetSection("JwtSettings");
            var key         = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSettings["Key"]!));
            var creds       = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

            var claims = new[]
            {
                new Claim(ClaimTypes.NameIdentifier, user.Id),
                new Claim(ClaimTypes.Email,           user.Email  ?? ""),
                new Claim(ClaimTypes.Name,            user.FullName ?? "")
            };

            var token = new JwtSecurityToken(
                issuer:             jwtSettings["Issuer"],
                audience:           jwtSettings["Audience"],
                claims:             claims,
                expires:            DateTime.UtcNow.AddHours(hours),
                signingCredentials: creds
            );

            return new JwtSecurityTokenHandler().WriteToken(token);
            
        }
// NEW
        [HttpPost("test/cleanup")]
        [AllowAnonymous]
        public async Task<IActionResult> TestCleanup()
        {
            var bypass = _config["TestSettings:OtpBypass"];
            if (string.IsNullOrEmpty(bypass)) return Forbid();

            var db = HttpContext.RequestServices.GetRequiredService<AppDbContext>();
            var testUser = await _userManager.FindByEmailAsync("test@saigonride.com");
            if (testUser == null) return NotFound();

            var activeRentals = await db.Rentals
                .Include(r => r.Vehicle)
                .Where(r => r.UserId == testUser.Id && (r.Status == RentalStatus.Active || r.Status == RentalStatus.Pending))
                .ToListAsync();

            foreach (var rental in activeRentals)
            {
                rental.Status = RentalStatus.Cancelled;
                if (rental.Vehicle != null)
                {
                    rental.Vehicle.Status = VehicleStatus.Available;
                    rental.Vehicle.StationId = rental.StartStationId;
                }
            }
            await db.SaveChangesAsync();
            return Ok(new { cancelled = activeRentals.Count });
        }
        public record TotpEnableRequest(string Code);
        public record TotpVerifyRequest(string PendingToken, string Code);
        public record SendOtpRequest(string Email);
        public record VerifyOtpRequest(string Email, string Otp);
    }
}
