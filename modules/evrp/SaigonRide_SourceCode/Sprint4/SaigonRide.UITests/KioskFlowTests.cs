using Microsoft.Playwright;
using Microsoft.Playwright.NUnit;
using NUnit.Framework;

[assembly: NonParallelizable]

[Parallelizable(ParallelScope.None)]
[TestFixture]

public class KioskFlowTests : PageTest
{
    private static readonly string BaseUrl =
        Environment.GetEnvironmentVariable("SAIGONRIDE_BASE_URL")
        ?? "http://localhost:5297";

    private static readonly string TestEmail =
        Environment.GetEnvironmentVariable("SAIGONRIDE_TEST_EMAIL")
        ?? "test@saigonride.com";

    private static readonly string TestOtp =
        Environment.GetEnvironmentVariable("SAIGONRIDE_TEST_OTP")
        ?? "123456";

    public override BrowserNewContextOptions ContextOptions() =>
        new()
        {
            ViewportSize      = new ViewportSize { Width = 1280, Height = 720 },
            RecordVideoDir    = "videos/",
            RecordVideoSize   = new RecordVideoSize { Width = 1280, Height = 720 }
        };

    // ── Helpers ────────────────────────────────────────────────────────────

    private async Task WaitForState(string name, int ms = 12000) =>
        await Page.Locator($"#paymentState_{name}").WaitForAsync(new()
        {
            State   = WaitForSelectorState.Visible,
            Timeout = ms
        });

    private async Task WaitForSplash(int ms = 12000)
    {
        await WaitForState("Splash", ms);
        await Page.WaitForFunctionAsync(
            "() => window.kioskReady === true",
            options: new() { Timeout = ms });
    }

    private async Task TypeOnNumpad(string targetInputId, string digits)
    {
        foreach (var d in digits)
            await Page.ClickAsync(
                $".numpad-key[data-target='{targetInputId}'][data-val='{d}']");
    }

    private async Task AuthThroughToVehicleSelect()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        await Page.FillAsync("#emailInput", TestEmail);
        await Page.ClickAsync("#btnSubmitEmail");
        await WaitForState("OtpInput");
        await TypeOnNumpad("otpInput", TestOtp);
        await Page.ClickAsync("#btnSubmitOtp");
        await WaitForState("AuthSuccess");
        await WaitForState("VehicleSelect", ms: 5000);
    }

    private async Task NavigateToIdle()
    {
        await AuthThroughToVehicleSelect();
        await Page.Locator(".vehicle-option-btn").First.ClickAsync();
        await WaitForState("DepositInfo");
        await Page.ClickAsync("#btnConfirmDeposit");
        await WaitForState("Idle");
    }

    // ── Kiosk flow ─────────────────────────────────────────────────────────

    [Test]
    public async Task Kiosk_Loads_And_Shows_Splash()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Expect(Page.Locator("#btnTouchToStart")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_EmailInput_Shows_After_Splash_Tap()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        await Expect(Page.Locator("#emailInput")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_EmailInput_Rejects_Invalid_Email()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        await Page.FillAsync("#emailInput", "notanemail");
        await Page.ClickAsync("#btnSubmitEmail");
        await Expect(Page.Locator("#emailError")).ToHaveTextAsync("Email không hợp lệ.");
        await Expect(Page.Locator("#paymentState_EmailInput")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_OtpInput_Shows_After_Valid_Email()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        await Page.FillAsync("#emailInput", TestEmail);
        await Page.ClickAsync("#btnSubmitEmail");
        await WaitForState("OtpInput");
        await Expect(Page.Locator("#otpInput")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_OtpInput_Rejects_Wrong_Code()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        await Page.FillAsync("#emailInput", TestEmail);
        await Page.ClickAsync("#btnSubmitEmail");
        await WaitForState("OtpInput");
        await TypeOnNumpad("otpInput", "000000");
        await Page.ClickAsync("#btnSubmitOtp");
        await Expect(Page.Locator("#otpError")).Not.ToBeEmptyAsync();
        await Expect(Page.Locator("#paymentState_OtpInput")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_VehicleSelect_Shows_After_Auth()
    {
        await AuthThroughToVehicleSelect();
        await Expect(Page.Locator(".vehicle-option-btn").First).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_DepositInfo_Shows_After_Vehicle_Selection()
    {
        await AuthThroughToVehicleSelect();
        await Page.Locator(".vehicle-option-btn").First.ClickAsync();
        await WaitForState("DepositInfo");
        await Expect(Page.Locator("#paymentState_DepositInfo .deposit-row").First).ToBeVisibleAsync();
        await Expect(Page.Locator("#btnConfirmDeposit")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_Idle_Shows_Payment_Method_Buttons()
    {
        await NavigateToIdle();
        await Expect(Page.Locator("#btnVietQR")).ToBeVisibleAsync();
        await Expect(Page.Locator("#btnStripe")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_VietQR_Shows_QR_And_Countdown()
    {
        await NavigateToIdle();
        await Page.ClickAsync("#btnVietQR");
        await WaitForState("Active");
        await Expect(Page.Locator("#countdownTimer")).ToBeVisibleAsync();
    }

    [Test]
    public async Task Kiosk_VietQR_Cancel_Returns_To_Idle()
    {
        await NavigateToIdle();
        await Page.ClickAsync("#btnVietQR");
        await WaitForState("Active");
        var cancelBtn = Page.Locator("#btnCancelRental");
        await cancelBtn.WaitForAsync(new() { State = WaitForSelectorState.Visible });
        await cancelBtn.ClickAsync();
        await WaitForState("Idle");
    }

    [Test]
    public async Task Kiosk_Stripe_Redirects_Or_Warns()
    {
        await NavigateToIdle();
        await Page.ClickAsync("#btnStripe");

        var checkoutTask = Page.WaitForURLAsync("**checkout.stripe.com**", new() { Timeout = 15000 })
                               .ContinueWith(_ => "checkout");
        var errorTask    = Page.Locator("#paymentState_Error")
                               .WaitForAsync(new() { State = WaitForSelectorState.Visible, Timeout = 15000 })
                               .ContinueWith(_ => "error");

        var winner = await await Task.WhenAny(checkoutTask, errorTask);
        if (winner == "checkout")
            Assert.That(Page.Url, Does.Contain("stripe.com"));
        else
            Assert.Warn("Stripe not configured — check Railway env vars.");
    }

    [Test]
    public async Task Kiosk_Error_State_Auto_Resets_After_10s()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.EvaluateAsync("() => window.goToState('Error', { message: 'Test error' })");
        await WaitForState("Error");
        await Expect(Page.Locator("#errorMessage")).ToHaveTextAsync("Test error");
        await WaitForState("Splash", ms: 15000);
    }
    [Test]
    public async Task Kiosk_Back_Button_Returns_To_Splash()
    {
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        await Page.ClickAsync("#btnTouchToStart");
        await WaitForState("EmailInput");
        var backBtn = Page.Locator("#paymentState_EmailInput [data-back-to='Splash']");
        await backBtn.WaitForAsync(new() { State = WaitForSelectorState.Visible });
        await backBtn.ClickAsync();
        await WaitForState("Splash");
    }

    // ── Web app ────────────────────────────────────────────────────────────

    [Test]
    public async Task WebApp_Home_Loads()
    {
        await Page.GotoAsync($"{BaseUrl}/");
        await Expect(Page.Locator(".hero-title")).ToBeVisibleAsync();
    }

    [Test]
    public async Task WebApp_Login_Page_Has_Form()
    {
        await Page.GotoAsync($"{BaseUrl}/Identity/Account/Login");
        await Expect(Page.Locator("#Input_Email")).ToBeVisibleAsync();
        await Expect(Page.Locator("#Input_Password")).ToBeVisibleAsync();
    }
    [Test]
    public async Task WebApp_Dashboard_Redirects_Unauthenticated_To_Login()
    {
        var context = await Browser.NewContextAsync(); // fresh context, no cookies
        var page = await context.NewPageAsync();
        await page.GotoAsync($"{BaseUrl}/Dashboard");
        await page.WaitForLoadStateAsync(LoadState.NetworkIdle);
        Assert.That(page.Url, Does.Contain("Login").IgnoreCase);
        await context.CloseAsync();
    } 
    [Test]
    public async Task Kiosk_Return_Flow_Shows_Receipt()
    {
        // Seed active rental
        var tokenRes = await Page.APIRequest.PostAsync($"{BaseUrl}/api/auth/verify-otp",
            new APIRequestContextOptions { DataObject = new { email = TestEmail, otp = TestOtp } });
        var tokenData = await tokenRes.JsonAsync();
        var token = tokenData?.GetProperty("token").GetString();

        // Cleanup first
        await Page.APIRequest.PostAsync($"{BaseUrl}/api/auth/test/cleanup");

        // Navigate kiosk to retrieve the station ID it is running on
        await Page.GotoAsync($"{BaseUrl}/Kiosk");
        await WaitForSplash();
        var stationIdStr = await Page.Locator("#kioskRoot").GetAttributeAsync("data-station-id");
        if (string.IsNullOrEmpty(stationIdStr) || !int.TryParse(stationIdStr, out var kioskStationId))
        {
            Assert.Fail("Could not retrieve station ID from kiosk UI.");
            return;
        }

        // Dynamically find an available vehicle at the kiosk's station
        var vehRes = await Page.APIRequest.GetAsync($"{BaseUrl}/api/vehicles?stationId={kioskStationId}",
            new APIRequestContextOptions { Headers = new Dictionary<string, string> { ["Authorization"] = $"Bearer {token}" } });
        
        if (!vehRes.Ok)
            Assert.Fail($"Failed to fetch vehicles. Status: {vehRes.Status}");

        var vehicles = await vehRes.JsonAsync();
        if (vehicles == null || vehicles.Value.GetArrayLength() == 0)
            Assert.Fail($"No available vehicles at station {kioskStationId} to start the return test.");

        var firstVehicle = vehicles.Value[0];
        var vehicleId = firstVehicle.GetProperty("id").GetInt32();
        var licensePlate = firstVehicle.GetProperty("licensePlate").GetString();

        var startRes = await Page.APIRequest.PostAsync($"{BaseUrl}/api/ride/start",
            new APIRequestContextOptions
            {
                Headers    = new Dictionary<string, string> { ["Authorization"] = $"Bearer {token}" },
                DataObject = new { vehicleId = vehicleId, stationId = kioskStationId, paymentMethod = "VietQR" }
            });

        if (!startRes.Ok)
        {
            var content = await startRes.TextAsync();
            Assert.Fail($"Could not start rental for return test. Status: {startRes.Status}, Body: {content}");
        }

        await Page.ClickAsync("#btnGoToReturn");
        await WaitForState("ReturnScan");

        await Page.EvaluateAsync($"() => {{ document.getElementById('bikeIdInput').value = '{licensePlate}'; }}");
        await Page.ClickAsync("#btnSubmitReturn");
        await WaitForState("ReturnProcessing");
        await WaitForState("ReturnReceipt", ms: 15000);
        await Expect(Page.Locator("#receiptFinalFare")).ToBeVisibleAsync();
    }
    
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
}