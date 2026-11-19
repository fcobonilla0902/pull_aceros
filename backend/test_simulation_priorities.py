import unittest
from statistics import mean

from pydantic import ValidationError
from simulation import Params, simulate, una_corrida


class PrioritySimulationTests(unittest.TestCase):
    def test_priority_means_include_every_replica(self):
        params = Params(solicitudes=150, porcentaje_urgentes=25, porcentaje_altas=25, replicas=3)
        result = simulate(params)
        records = [record for i in range(params.replicas)
                   for record in una_corrida(params, params.semilla+i)['registros']]
        for priority, summary in result['por_prioridad'].items():
            group = [record for record in records if record['prioridad'] == priority]
            self.assertEqual(summary['solicitudes'], len(group))
            self.assertEqual(summary['tiempo_total_promedio'], round(mean(r['duracion'] for r in group), 2))
            self.assertEqual(summary['espera_promedio'], round(mean(r['espera'] for r in group), 2))

    def test_absent_priorities_have_no_time(self):
        result = simulate(Params(porcentaje_urgentes=0, porcentaje_altas=0))
        self.assertIsNone(result['por_prioridad']['alta']['tiempo_total_promedio'])
        self.assertEqual(result['por_prioridad']['urgente']['solicitudes'], 0)
        self.assertEqual(result['por_prioridad']['normal']['solicitudes'], 500)

    def test_same_workload_across_forklift_counts(self):
        params = Params(solicitudes=100, porcentaje_urgentes=25, porcentaje_altas=25)
        workload = lambda rows: [(r['llegada'], r['prioridad'], r['preparacion'], r['traslado']) for r in rows]
        baseline = workload(una_corrida(params, 42)['registros'])
        for count in range(1, 5):
            self.assertEqual(baseline, workload(una_corrida(params.model_copy(update={'montacargas': count}), 42)['registros']))

    def test_invalid_priority_mix(self):
        with self.assertRaises(ValidationError):
            Params(porcentaje_urgentes=80, porcentaje_altas=30)


if __name__ == '__main__':
    unittest.main()
