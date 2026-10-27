import unittest
import test_accounts as fixtures
import server


class BuiltinKpiTests(fixtures.AccountTests):
    test_slow_dax_does_not_block_table_or_custom_visual_queries = None
    test_report_isolation_and_administration = None
    test_report_sharing_grants_and_revokes_read_access = None
    test_passwords_sessions_and_legacy_ownership = None
    test_package_isolation_and_session_expiry = None

    def test_builtin_requires_auth_but_is_available_to_normal_accounts(self):
        anonymous=fixtures.Client(self.httpd)
        self.assertEqual(anonymous.request('GET','/api/builtin-visuals')[0],401)
        user,client=self.create_user('kpireader')
        status,packages=client.request('GET','/api/builtin-visuals')
        self.assertEqual(status,200)
        self.assertEqual(len(packages),1)
        package=packages[0]
        self.assertTrue(package['builtin'])
        self.assertNotIn('js',package)
        endpoint='/api/custom-visuals/'+package['id']
        self.assertEqual(anonymous.request('GET',endpoint)[0],401)
        self.assertEqual(client.request('GET',endpoint)[1]['guid'],package['guid'])
        self.assertEqual(client.request('GET','/api/custom-visuals')[1],[])


if __name__=='__main__':unittest.main()
