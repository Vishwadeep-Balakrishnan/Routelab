from routelab import Route, RouteLabSession, ResponseSpec

session = RouteLabSession(event_log_path="traffic.jsonl")

@session.before_request
def add_trace(req):
    req.headers["x-trace-id"] = "example-run"
    return req

session.add(
    Route.named("mock-health")
    .matching(path="/health")
    .mock(ResponseSpec.json({"status": "ok"}))
)

client = session.client()
response = client.get("https://api.example.com/health")
print(response.json())
