import os
cwd = os.getcwd()
import sys
sys.path.append(cwd + '/src')

import pytest
import requests
import time
import zlib
from metrics_config import MetricsConfig, ConfigOptions
from metrics_sender import MetricsSender, HeaderKeys
from metrics_buffer import MetricsBuffer
from collectd.collectd_config import CollectdConfig, ConfigNode
from collectd.helper import Helper


def test_post_normal_no_additional_header():
    met_buffer = MetricsBuffer(10)
    helper = Helper()

    for i in range(10):
        met_buffer.put_pending_batch(['batch_%s' % i])

    met_sender = MetricsSender(helper.conf, met_buffer)

    sleep_helper(10, 0.100, 100)

    assert requests.mock_server.url == helper.conf[ConfigOptions.url]
    assert requests.mock_server.headers == {
        HeaderKeys.content_type: helper.conf[ConfigOptions.content_type],
        HeaderKeys.content_encoding: helper.conf[ConfigOptions.content_encoding]
    }
    for i in range(10):
        assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i

    met_sender.cancel_timer()


def test_post_normal_additional_keys():
    met_buffer = MetricsBuffer(10)
    met_config = MetricsConfig()

    configs = {
        'source_name': 'test_source',
        'host_name': 'test_host',
        'source_category': 'test_category'
    }
    Helper.parse_configs(met_config, configs)

    for i in range(10):
        met_buffer.put_pending_batch(['batch_%s' % i])

    met_sender = MetricsSender(met_config.conf, met_buffer)

    sleep_helper(10, 0.100, 100)

    assert requests.mock_server.url == met_config.conf[ConfigOptions.url]
    assert requests.mock_server.headers == {
        HeaderKeys.content_type: met_config.conf[ConfigOptions.content_type],
        HeaderKeys.content_encoding: met_config.conf[ConfigOptions.content_encoding],
        HeaderKeys.x_sumo_source: 'test_source',
        HeaderKeys.x_sumo_host: 'test_host',
        HeaderKeys.x_sumo_category: 'test_category'
    }

    for i in range(10):
        assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i

    met_sender.cancel_timer()


def test_post_normal_addition_dimensions_metadata():
    met_buffer = MetricsBuffer(10)
    met_config = MetricsConfig()

    configs = {
        'dimension_tags': ('dim_key1', 'dim_val1', 'dim_key2', 'dim_val2'),
        'meta_tags': ('meta_key1', 'meta_val1', 'meta_key2', 'meta_val2')
    }
    for (key, value) in configs.items():
        node = ConfigNode(getattr(ConfigOptions, key), value)
        config = CollectdConfig([Helper.url_node(), node])
        met_config.parse_config(config)

    for i in range(10):
        met_buffer.put_pending_batch(['batch_%s' % i])

    met_sender = MetricsSender(met_config.conf, met_buffer)

    sleep_helper(10, 0.100, 100)

    assert requests.mock_server.url == met_config.conf[ConfigOptions.url]
    assert requests.mock_server.headers == {
        HeaderKeys.content_type: met_config.conf[ConfigOptions.content_type],
        HeaderKeys.content_encoding: met_config.conf[ConfigOptions.content_encoding],
        HeaderKeys.x_sumo_dimensions: 'dim_key1=dim_val1 dim_key2=dim_val2',
        HeaderKeys.x_sumo_metadata: 'meta_key1=meta_val1 meta_key2=meta_val2',
    }

    for i in range(10):
        assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i

    met_sender.cancel_timer()


def test_post_client_recoverable_http_error():
    error_codes = [404, 408, 429]
    for error_code in error_codes:
        reset_test_env()
        exception_to_raise = requests.exceptions.HTTPError(requests.exceptions.RequestException())
        requests.mock_response.status_code = error_codes
        met_buffer = MetricsBuffer(10)
        helper_test_post_recoverable_exception(met_buffer, exception_to_raise, error_code, 5)
        for i in range(10):
            assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i


def test_post_server_recoverable_http_error():
    error_codes = [500, 502, 503, 504, 506, 507, 508, 510, 511]

    for error_code in error_codes:
        reset_test_env()
        exception_to_raise = requests.exceptions.HTTPError(requests.exceptions.RequestException())
        requests.mock_response.status_code = error_code
        met_buffer = MetricsBuffer(10)
        helper_test_post_recoverable_exception(met_buffer, exception_to_raise, error_code, 5)
        for i in range(10):
            assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i


def test_post_unrecoverable_http_error():
    request_exception = requests.exceptions.RequestException()
    exception_cases = [requests.exceptions.HTTPError(request_exception)]

    for exception_case in exception_cases:
        reset_test_env()
        helper_test_post_unrecoverable_exception(exception_case, "unknown_status_code")


def test_post_recoverable_requests_exception():
    request_exception = requests.exceptions.RequestException()
    exception_cases = [requests.exceptions.ConnectionError(request_exception),
                       requests.exceptions.Timeout(request_exception),
                       requests.exceptions.TooManyRedirects(request_exception),
                       requests.exceptions.StreamConsumedError(request_exception),
                       requests.exceptions.RetryError(request_exception),
                       requests.exceptions.ChunkedEncodingError(request_exception),
                       requests.exceptions.ContentDecodingError(request_exception)]

    for exception_case in exception_cases:
        reset_test_env()
        met_buffer = MetricsBuffer(10)
        helper_test_post_recoverable_exception(met_buffer, exception_case, "unknown_status_code", 5)
        for i in range(10):
            assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i


def test_post_unrecoverable_requests_exception():
    request_exception = requests.exceptions.RequestException()
    exception_cases = [requests.exceptions.URLRequired(request_exception),
                       requests.exceptions.MissingSchema(request_exception),
                       requests.exceptions.InvalidSchema(request_exception),
                       requests.exceptions.InvalidURL(request_exception),
                       Exception('unknown_exception')]

    for exception_case in exception_cases:
        reset_test_env()
        helper_test_post_unrecoverable_exception(exception_case, "unknown_status_code")


def test_post_fail_after_retries_with_buffer_full():
    met_buffer = MetricsBuffer(10)
    met_buffer.put_pending_batch(['batch_first'])
    exception_to_raise = requests.exceptions.HTTPError(requests.exceptions.RequestException())
    helper_test_post_recoverable_exception(met_buffer, exception_to_raise, 429, 10)
    for i in range(10):
        assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % i


def test_post_fail_after_retries_with_buffer_not_full():
    met_buffer = MetricsBuffer(20)
    met_buffer.put_pending_batch(['batch_first'])
    exception_to_raise = requests.exceptions.HTTPError(requests.exceptions.RequestException())
    helper_test_post_recoverable_exception(met_buffer, exception_to_raise, 429, 10)

    assert zlib.decompress(requests.mock_server.data[0]) == 'batch_first'
    for i in range(1, 10):
        assert zlib.decompress(requests.mock_server.data[i]) == 'batch_%s' % (i - 1)


#
# Helper functions
#

@pytest.fixture(scope="function", autouse=True)
def reset_response_decider_and_fake_server():
    reset_test_env()


def reset_test_env():
    requests.post_response_decider.reset()
    requests.mock_server.reset()
    requests.mock_response.reset()


def helper_test_post_recoverable_exception(met_buffer, exception, error_code,
                                           stop_raise_exception_after):
    met_config = MetricsConfig()

    configs = {
        'retry_initial_delay': '0',
        'retry_max_attempts': '5',
        'retry_max_delay': '5',
        'retry_backoff': '1',
        'retry_jitter_min': '0',
        'retry_jitter_max': '0'
    }
    Helper.parse_configs(met_config, configs)

    requests.post_response_decider.set(True, False, exception, stop_raise_exception_after, 0)
    requests.mock_response.set(error_code)

    for i in range(10):
        met_buffer.put_pending_batch(['batch_%s' % i])

    met_sender = MetricsSender(met_config.conf, met_buffer)

    sleep_helper(10, 0.100, 100)

    assert requests.mock_server.url == met_config.conf[ConfigOptions.url]
    assert requests.mock_server.headers == {
        HeaderKeys.content_type: met_config.conf[ConfigOptions.content_type],
        HeaderKeys.content_encoding: met_config.conf[ConfigOptions.content_encoding]
    }

    met_sender.cancel_timer()


def helper_test_post_unrecoverable_exception(exception, error_code):
    with pytest.raises(Exception) as e:
        met_buffer = MetricsBuffer(10)
        helper = Helper()

        requests.mock_response.set(error_code)
        requests.post_response_decider.set(False, True, exception, 5, 0)

        for i in range(10):
            met_buffer.put_pending_batch(['batch_%s' % i])

        MetricsSender(helper.conf, met_buffer)

    assert e.type == type(exception)


def sleep_helper(expected_data_size, sleep_interval, max_tries):
    current_retry = 0
    while len(requests.mock_server.data) != expected_data_size \
            and current_retry < max_tries:
        time.sleep(sleep_interval)
        current_retry += 1