import unittest
from edfa_controller import input_power_display, output_power_display, parse_answer

class ProtocolTests(unittest.TestCase):
    def test_parse_value(self): self.assertEqual(parse_answer("PUE=245\r"), "245")
    def test_parse_ack(self): self.assertEqual(parse_answer("CPU!\r"), "OK")
    def test_input(self): self.assertEqual(input_power_display("245"), "245 µW   (-6.11 dBm)")
    def test_output(self): self.assertEqual(output_power_display("2000"), "2000 mW   (33.01 dBm)")
    def test_unsupported(self):
        with self.assertRaises(ValueError): parse_answer("IPW/")

if __name__ == "__main__": unittest.main()

