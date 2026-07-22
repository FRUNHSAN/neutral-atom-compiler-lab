# ZAP vs NAC — Fig.7 ~ Fig.14 对比总表

| 图 | 内容 | ZAP | NAC | 关键差异 |
|---|---|---|---|---|
| Fig.7 | 保真度分解(14bench) | F_2q/F_idle/F_tr/F_dec堆叠 | 同公式,F_2q 100%一致 | 13/14 +-5%, sat_n11 +6.4% |
| Fig.8 | 随机3-正则scaling | N=10->100 fidelity趋势 | 同趋势,F_tr低5-10% | 随机图无结构,placer权重均匀化 |
| Fig.9 | 编译器依赖通道 | F_idle x F_tr x F_dec | 同度量 | NAC偏F_tr(少搬),ZAP偏F_idle |
| Fig.10 | 执行时间 | ZAP baseline | NAC系统性偏短10-37% | alpha=1.0偏留着,少搬->快 |
| Fig.11 | 编译时间 | <0.3s | 0.02-0.3s(小电路慢2-3x) | Cat/Adder反而快2-5x |
| Fig.12 | 可扩展性(->500q) | Ising 0.6->30s O(N) | Ising 1.3->50s O(N) | 同O(N),大Cat快5x,大Adder快2x |
| Fig.13 | 消融(3策略) | baseline ~ always_move | 3策略可切换 | alpha=1.0偏stay,NAC baseline < always_move |
| Fig.14 | 灵敏度热力图 | ZAP vs PM ERR | baseline vs always_move ERR | ERR全负~-0.1,默认点星标 |
