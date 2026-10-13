using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;
using OtpNet;

namespace SaigonRide.UITests;

[Parallelizable(ParallelScope.None)]
[TestFixture]
public class TotpFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

    private static readonly string TestEmail =
        Environment.GetEnvironmentVariable("SAIGONRIDE_TOTP_EMAIL")
        ?? "totp_test@saigonride.com";

    private static readonly string TestPassword =
        Environment.GetEnvironmentVariable("SAIGONRIDE_TOTP_PASSWORD")
        ?? "Test@1234567!";

    // Known fixed secret seeded for the test user
    private static readonly string TestTotpSecret =
        Environment.GetEnvironmentVariable("SAIGONRIDE_TOTP_SECRET")
        ?? "JBSWY3DPEHPK3PXP";

    public override BrowserNewContextOptions ContextOptions() =>
        new() { ViewportSize = new ViewportSize { Width = 1280, Height = 720 } };

    [TearDown]
    public async Task TearDown()
    {
        if (TestContext.CurrentContext.Result.Outcome.Status == NUnit.Framework.Interfaces.TestStatus.Failed)
        {
            Directory.CreateDirectory("screenshots");
            await Page.ScreenshotAsync(new PageScreenshotOptions
            {
                Path = $"screenshots/{TestContext.CurrentContext.Test.Name}_{DateTime.Now:HHmmss}.png"
            });
        }
    }

    private string GenerateTotp()
    {
        var secretBytes = Base32Encoding.ToBytes(TestTotpSecret);
        var totp        = new Totp(secretBytes);
        return totp.ComputeTotp();
    }

    // ── Web app TOTP flow ───────────────────────────────────────────────────

    [Test]
    public async Task WebApp_Login_With_Totp_Succeeds()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    TestEmail);
        await Page.FillAsync("#Input_Password", TestPassword);
        await Page.ClickAsync("button[type='submit']");

        // Should land on 2FA page
        await Page.WaitForURLAsync("**/LoginWith2fa**");
        await Expect(Page.Locator("input[name='Input.TotpCode']")).ToBeVisibleAsync();

        await Page.FillAsync("input[name='Input.TotpCode']", GenerateTotp());
        await Page.ClickAsync("button[type='submit']");

        await Page.WaitForURLAsync("**/Dashboard**");
        await Expect(Page.Locator(".dash-name")).ToBeVisibleAsync();
    }

    [Test]
    public async Task WebApp_Login_Totp_Rejects_Wrong_Code()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    TestEmail);
        await Page.FillAsync("#Input_Password", TestPassword);
        await Page.ClickAsync("button[type='submit']");

        await Page.WaitForURLAsync("**/LoginWith2fa**");
        await Page.FillAsync("input[name='Input.TotpCode']", "000000");
        await Page.ClickAsync("button[type='submit']");

        await Expect(Page.Locator(".validation-summary-errors")).ToBeVisibleAsync();
        Assert.That(Page.Url, Does.Contain("LoginWith2fa"));
    }

    [Test]
    public async Task WebApp_Login_Totp_Session_Expires_On_Back()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    TestEmail);
        await Page.FillAsync("#Input_Password", TestPassword);
        await Page.ClickAsync("button[type='submit']");

        await Page.WaitForURLAsync("**/LoginWith2fa**");

        // Navigate directly to login instead — session should not persist
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Expect(Page.Locator("#Input_Email")).ToBeVisibleAsync();
    }

    // ── Security settings ───────────────────────────────────────────────────

    [Test]
    public async Task Security_Page_Shows_Totp_Status()
    {
        // Login normally with TOTP first
        await LoginWithTotp();
        await Page.GotoAsync($"{BaseUrl}/Security");
        await Expect(Page.Locator("body")).ToContainTextAsync("Authenticator App");
    }

    // ── Helper ──────────────────────────────────────────────────────────────

    private async Task LoginWithTotp()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    TestEmail);
        await Page.FillAsync("#Input_Password", TestPassword);
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForURLAsync("**/LoginWith2fa**");
        await Page.FillAsync("input[name='Input.TotpCode']", GenerateTotp());
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForURLAsync("**/Dashboard**");
    }
}