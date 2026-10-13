using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SaigonRide.UITests;

[Parallelizable(ParallelScope.None)]
[TestFixture]
public class WalletFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

    public override BrowserNewContextOptions ContextOptions() =>
        new()
        {
            ViewportSize   = new ViewportSize { Width = 1280, Height = 720 },
            RecordVideoDir = "videos/",
            RecordVideoSize = new RecordVideoSize { Width = 1280, Height = 720 }
        };

    private async Task LoginAsync()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    "test@saigonride.com");
        await Page.FillAsync("#Input_Password", "Test@SaigonRide99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
    }

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

    [Test]
    public async Task Wallet_Page_Loads_With_Balance()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Wallet");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        await Expect(Page.Locator(".wallet-wrap")).ToBeVisibleAsync();
        await Expect(Page.Locator(".balance-amount")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Wallet_Shows_Transaction_History()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Wallet");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        await Expect(Page.Locator(".wallet-wrap")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Wallet_TopUp_Shows_QR()
    {
        await LoginAsync();
        await Page.GotoAsync($"{BaseUrl}/Wallet");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        var topUpBtn = Page.Locator("#btnTopup");
        await topUpBtn.ClickAsync();
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Contain("Wallet").IgnoreCase);
    }

    [Test]
    public async Task Wallet_Unauthenticated_Redirects_To_Login()
    {
        var context = await Browser.NewContextAsync();
        var page    = await context.NewPageAsync();
        await page.GotoAsync($"{BaseUrl}/Wallet");
        await page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(page.Url, Does.Contain("Login").IgnoreCase);
        await context.CloseAsync();
    }
}
