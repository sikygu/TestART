
failure_types = [
    "org.junit.Assert.assertEquals",
    (["org.junit.Assert.assertTrue", "org.junit.Assert.assertFalse"], "assertTrue/False"),
    (["org.junit.Assert.assertNotNull", "org.junit.Assert.assertNull"], "assertNull/NotNull"),
    (["org.mockito.exceptions","Argument(s) are different!","Wanted but not invoked"], "mockito"),
    "org.junit.Assert.assertThat",
    "org.junit.Assert.fail",
    (["java.lang.AssertionError: Expected","java.lang.AssertionError: expected", "java.lang.AssertionError: unexpected", r"java.lang.AssertionError\r\n\tat"], "wtf"),

]
msg_list = [
        """[INFO]  T E S T S
[ERROR] Tests run: 1, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.145 s <<< FAILURE! -- in org.jfree.chart.text.TextBlockTest\r\n[ERROR] org.jfree.chart.text.TextBlockTest.testCa
        at org.junit.Assert.assertTrue
        """
    ]
msg_list = [
    x for x in msg_list
    if "[INFO]  T E S T S" in x
]
status = "PASS"
pattern = r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)"
import re
def get_exec_tuple(message: str):
    match = re.search(pattern, message)
    if match:
        return tuple(map(int, match.groups()))
    return (0, 0, 0)
failure_sets = []
for msg in msg_list:
    failure_set = set()
    t = get_exec_tuple(msg)
    if t[1] + t[2] == 0:
        continue
    flag = False
    if t[2] > 0:
        failure_sets.append({"error"})
        continue
    for failure_type in failure_types:
        if isinstance(failure_type, tuple):
            for sub_failure_type in failure_type[0]:
                if sub_failure_type in msg:
                    flag = True
                    failure_set.add(sub_failure_type)
                    break
        elif failure_type in msg:
            flag = True
            failure_set.add(failure_type)
            break
        if flag:
            break
    if flag:
        try:
            assert len(failure_set) == 1
        except:
            print(failure_set)
            print(msg)
            assert False
    if not flag:
        print(msg.split("<<< FAILURE!"))
        assert False
    failure_sets.append(failure_set)

    # 最后失败的set内容
    last_failure_set = failure_sets[-1]
    # 对最后一个赋予RUNTIME_ERROR
    failure_sets[-1].add(status)
    # 对前几个和最后一个内容相同的set赋予RUNTIME_ERROR
    for i in range(len(failure_sets) - 1):
        if failure_sets[i] == last_failure_set:
            failure_sets[i].add(status)
    # 对没有RUNTIME_ERROR的赋予PASS
    for i in range(len(failure_sets)):
        if len(failure_sets[i]) == 1:
            failure_sets[i].add("PASS")
    # if flag:
    #     break
print(failure_sets)