#include <zephyr/ztest.h>

extern struct ztest_suite_stats UTIL_CAT(z_ztest_suite_node_stats_, testsuite);
struct ztest_suite_stats *suite_stats = &UTIL_CAT(z_ztest_suite_node_stats_, testsuite);
extern struct ztest_unit_test_stats z_ztest_unit_test_stats_testsuite_test_repeating1;
struct ztest_unit_test_stats *case_stats = &z_ztest_unit_test_stats_testsuite_test_repeating1;

ZTEST(testsuite, test_repeating1)
{
	ztest_test_pass();
}

ZTEST(testsuite, test_repeating2)
{
	ztest_test_pass();
}

ZTEST(testsuite, test_repeating3)
{
	ztest_test_pass();
}

static void repeat_teardown(void *)
{
	/* run_count + 1 counter is incremented after the testcase is executed. */
	printk("Test suite executed: %d times.\n", suite_stats->run_count + 1);
	printk("Test case executed : %d times.\n", case_stats->run_count);
}

ZTEST_SUITE(testsuite, NULL, NULL, NULL, NULL, repeat_teardown);
