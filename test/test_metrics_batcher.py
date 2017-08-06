import os
cwd = os.getcwd()
import sys
sys.path.append(cwd + '/src')
import time
from metrics_buffer import MetricsBuffer
from metrics_batcher import MetricsBatcher


def test_metrics_batcher_max_size():
    met_buffer = MetricsBuffer(100)
    max_batch_size = 10
    met_batcher = MetricsBatcher(max_batch_size, 60.0, met_buffer)

    for i in range(50):
        met_batcher.push_item('item_%s' % i)

    assert met_buffer.pending_queue.qsize() == 5
    for i in range(5):
        batch = met_buffer.get_batch()

        expected_batch = []
        for j in range(max_batch_size):
            expected_batch.append('item_%s' % (i * max_batch_size + j))

        assert len(batch) == max_batch_size
        assert batch == expected_batch

    met_batcher.cancel_timer()


def test_metrics_batcher_max_interval():
    met_buffer = MetricsBuffer(100)
    max_batch_interval = 0.05
    met_batcher = MetricsBatcher(1000, max_batch_interval, met_buffer)

    for i in range(50):
        time.sleep(0.010)
        met_batcher.push_item('item_%s' % i)

    while not met_buffer.pending_queue.empty():
        batch = met_buffer.pending_queue.get()
        assert len(batch) < 10

    met_batcher.cancel_timer()


def test_metrics_batcher_locks():
    met_buffer = MetricsBuffer(25)
    max_batch_size = 2
    met_batcher = MetricsBatcher(max_batch_size, 0.100, met_buffer)

    for i in range(50):
        met_batcher.push_item('item_%s' % i)

    assert met_buffer.pending_queue.qsize() == 25
    for i in range(25):
        batch = met_buffer.get_batch()

        expected_batch = []
        for j in range(max_batch_size):
            expected_batch.append('item_%s' % (i * max_batch_size + j))

        assert len(batch) == max_batch_size
        assert batch == expected_batch

    met_batcher.cancel_timer()
