namespace StreamSuites.DesktopAdmin.Runtime.Services
{
    public sealed class CloudflareTunnelServiceController : RuntimeServiceController
    {
        public CloudflareTunnelServiceController()
            : base("Cloudflare Tunnel", "cloudflared", "tunnel run streamsuites-api")
        {
        }
    }
}
