using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SaigonRide.UITests;

[Parallelizable(ParallelScope.None)]
[TestFixture]
public class MobileFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

    public override BrowserNewContextOptions ContextOptions() =>
        new()
        {
            ViewportSize      = new ViewportSize { Width = 390, Height = 844 },
            UserAgent         = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            IsMobile          = true,
            HasTouch          = true,
            DeviceScaleFactor = 3,
            RecordVideoDir    = "videos/",
            RecordVideoSize   = new RecordVideoSize { Width = 390, Height = 844 }
        };

    [TearDown]
    public async Task TearDown()
    {
        if (TestContext.CurrentContext.Result.Outcome.Status == NUnit.Framework.Interfaces.TestStatus.Failed)
        {
            var dir = "screenshots";
            Directory.CreateDirectory(dir);
            await Page.ScreenshotAsync(new PageScreenshotOptions
            {
                Path = $"{dir}/{TestContext.CurrentContext.Test.Name}_{DateTime.Now:HHmmss}.png"
            });
        }
        try { await Page.APIRequest.PostAsync($"{BaseUrl}/api/auth/test/cleanup"); }
        catch { }
    }

    [Test]
    public async Task Mobile_Home_Loads()
    {
        await Page.GotoAsync($"{BaseUrl}/");
        await Expect(Page.Locator(".hero-title")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Mobile_Login_Page_Has_Form()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Expect(Page.Locator("#Input_Email")).ToBeVisibleAsync();
        await Expect(Page.Locator("#Input_Password")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Mobile_Login_Succeeds_And_Redirects_To_Dashboard()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    "test@saigonride.com");
        await Page.FillAsync("#Input_Password", "Test@SaigonRide99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Contain("Dashboard").IgnoreCase);
    }
    [Test]
    public async Task Mobile_Dashboard_Shows_Balance_And_Stats()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Dashboard");
        await Expect(Page.Locator(".balance-amount")).ToBeVisibleAsync();
        await Expect(Page.Locator(".stats-row")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Mobile_Wallet_Page_Loads()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Wallet");
        await Expect(Page.Locator(".wallet-wrap")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Mobile_Security_Page_Loads()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Security");
        await Expect(Page.Locator("body")).ToContainTextAsync("Authenticator App");
    }

    [Test]
    public async Task Mobile_Dashboard_Redirects_Unauthenticated()
    {
        var context = await Browser.NewContextAsync(ContextOptions());
        var page    = await context.NewPageAsync();
        await page.GotoAsync($"{BaseUrl}/Dashboard");
        await page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(page.Url, Does.Contain("Login").IgnoreCase);
        await context.CloseAsync();
    }
    private async Task LoginAsync()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    "test@saigonride.com");
        await Page.FillAsync("#Input_Password", "Test@SaigonRide99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        // If still on login page, dump current URL for debugging
        if (Page.Url.Contains("Login"))
            Assert.Fail($"Login failed, still at: {Page.Url}");
    }
}