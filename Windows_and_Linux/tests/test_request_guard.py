import threading
import unittest

from request_guard import RequestGenerationGuard


class RequestGenerationGuardTests(unittest.TestCase):
    def test_only_newest_request_is_current(self):
        guard = RequestGenerationGuard()
        first = guard.begin()
        second = guard.begin()

        self.assertFalse(guard.is_current(first))
        self.assertTrue(guard.is_current(second))
        self.assertFalse(guard.is_current(0))

    def test_concurrent_request_ids_are_unique_and_monotonic(self):
        guard = RequestGenerationGuard()
        identifiers = []
        identifiers_lock = threading.Lock()

        def begin_request():
            request_id = guard.begin()
            with identifiers_lock:
                identifiers.append(request_id)

        threads = [threading.Thread(target=begin_request) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(identifiers), list(range(1, 21)))
        self.assertTrue(guard.is_current(20))


if __name__ == "__main__":
    unittest.main()
