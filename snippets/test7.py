# class Thing:
#     foo = 1

#     def __init__(self):
#         self.bar = 2

#     def doThing(self):
#         self.baz = 3
#         # print(f"{self.baz} is set")

# # class Thing2:

# #     def doThing2(self, attr):
# #         print(attr)


# a = Thing()
# print(**a)
# b = Thing2()
# a.doThing()
# b.doThing2(a.baz)

# try:
#     1/0
# except TypeError:
#     print("type error")

# print("after try block")
data_dict = {"info": "1.0.0", "items": ""}
for item in data_dict["items"]:
    print(item)