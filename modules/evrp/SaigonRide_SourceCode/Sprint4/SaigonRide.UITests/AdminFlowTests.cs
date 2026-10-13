using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SaigonRide.UITests;

[Parallelizable(ParallelScope.None)]
[TestFixture]
public class AdminFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

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

    private async Task LoginAsAdmin()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    "admin@saigonride.com");
        await Page.FillAsync("#Input_Password", "Admin@SaigonRide99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
    }

    [Test]
    public async Task Admin_Login_Redirects_To_Dashboard()
    {
        await LoginAsAdmin();
        Assert.That(Page.Url, Does.Contain("Dashboard").IgnoreCase);
    }

    [Test]
    public async Task Admin_Can_Access_Admin_Panel()
    {
        await LoginAsAdmin();
        await Page.GotoAsync($"{BaseUrl}/Admin");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Contain("Admin").IgnoreCase);
    }

    [Test]
    public async Task Admin_Panel_Shows_Station_Metrics()
    {
        await LoginAsAdmin();
        await Page.GotoAsync($"{BaseUrl}/Admin");
        await Expect(Page.Locator("body")).ToContainTextAsync("Bến Thành");
    }

    [Test]
    public async Task Admin_Panel_Shows_Vehicle_Stats()
    {
        await LoginAsAdmin();
        await Page.GotoAsync($"{BaseUrl}/Admin");
        await Expect(Page.Locator("body")).ToContainTextAsync("Standard Bike");
    }

    [Test]
    public async Task Admin_Unauthenticated_Redirects_To_Login()
    {
        var context = await Browser.NewContextAsync();
        var page    = await context.NewPageAsync();
        await page.GotoAsync($"{BaseUrl}/Admin");
        await page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(page.Url, Does.Contain("Login").IgnoreCase);
        await context.CloseAsync();
    }

    [Test]
    public async Task Admin_Regular_User_Cannot_Access_Admin_Panel()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Page.FillAsync("#Input_Email",    "test@saigonride.com");
        await Page.FillAsync("#Input_Password", "Test@SaigonRide99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        await Page.GotoAsync($"{BaseUrl}/Admin");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Not.Contain("Admin/Index").IgnoreCase);
    }
}