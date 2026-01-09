# ChatGPT 军人 SheerID 验证配置文件

# SheerID API 配置
SHEERID_BASE_URL = 'https://services.sheerid.com'
MY_SHEERID_URL = 'https://my.sheerid.com'

# 军人状态选项
MILITARY_STATUSES = [
    'VETERAN',           # 退役军人
    'ACTIVE_DUTY',       # 现役军人
    'RESERVE',           # 预备役
]

# 默认使用退役军人状态
DEFAULT_MILITARY_STATUS = 'VETERAN'

# 军队组织配置
ORGANIZATIONS = {
    '4070': {
        'id': 4070,
        'idExtended': '4070',
        'name': 'Army',
        'country': 'US',
        'type': 'MILITARY',
    },
    '4073': {
        'id': 4073,
        'idExtended': '4073',
        'name': 'Air Force',
        'country': 'US',
        'type': 'MILITARY',
    },
    '4072': {
        'id': 4072,
        'idExtended': '4072',
        'name': 'Navy',
        'country': 'US',
        'type': 'MILITARY',
    },
    '4071': {
        'id': 4071,
        'idExtended': '4071',
        'name': 'Marine Corps',
        'country': 'US',
        'type': 'MILITARY',
    },
    '4074': {
        'id': 4074,
        'idExtended': '4074',
        'name': 'Coast Guard',
        'country': 'US',
        'type': 'MILITARY',
    },
    '4544268': {
        'id': 4544268,
        'idExtended': '4544268',
        'name': 'Space Force',
        'country': 'US',
        'type': 'MILITARY',
    },
}

# 默认组织（Army）
DEFAULT_ORGANIZATION_ID = '4070'

# 组织ID列表（用于随机选择）
ORGANIZATION_IDS = list(ORGANIZATIONS.keys())
