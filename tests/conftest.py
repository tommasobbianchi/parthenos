def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: scale/performance tests, run with -m benchmark")
