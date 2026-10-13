using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

namespace SaigonRide.UITests;

[Parallelizable(ParallelScope.None)]
[TestFixture]
public class RegistrationFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

    public override BrowserNewContextOptions ContextOptions() =>
        new()
        {
            ViewportSize    = new ViewportSize { Width = 1280, Height = 720 },
            RecordVideoDir  = "videos/",
            RecordVideoSize = new RecordVideoSize { Width = 1280, Height = 720 }
        };

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
    public async Task Register_Page_Loads()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Register");
        await Expect(Page.Locator("#Input_Email")).ToBeVisibleAsync();
        await Expect(Page.Locator("#Input_Password")).ToBeVisibleAsync();
        await Expect(Page.Locator("#Input_ConfirmPassword")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Register_With_Invalid_Email_Shows_Error()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Register");
        await Page.FillAsync("#Input_Email",           "notanemail");
        await Page.FillAsync("#Input_Password",        "Test@1234567!");
        await Page.FillAsync("#Input_ConfirmPassword", "Test@1234567!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Contain("Register").IgnoreCase);
    }

    [Test]
    public async Task Register_With_Mismatched_Passwords_Shows_Error()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Register");
        await Page.FillAsync("#Input_Email",           $"newuser_{Guid.NewGuid():N}@test.com");
        await Page.FillAsync("#Input_Password",        "Test@1234567!");
        await Page.FillAsync("#Input_ConfirmPassword", "DifferentPass@99!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Contain("Register").IgnoreCase);
    }

    [Test]
    public async Task Register_New_User_Succeeds_And_Redirects()
    {
        var uniqueEmail = $"playwright_{Guid.NewGuid():N}@saigonride.com";
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Register");
        await Page.FillAsync("#Input_Email",           uniqueEmail);
        await Page.FillAsync("#Input_Password",        "Test@1234567!");
        await Page.FillAsync("#Input_ConfirmPassword", "Test@1234567!");
        await Page.ClickAsync("button[type='submit']");
        await Page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(Page.Url, Does.Not.Contain("Register").IgnoreCase);
    }
}
