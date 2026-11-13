"""Provider adapters. Each turns one SDK into the `ChatProvider` protocol and translates that
SDK's exceptions into `app.llm.errors`, so nothing provider-specific leaks upward."""
