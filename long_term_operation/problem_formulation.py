from numpy import array, vstack, zeros
import numpy
from configuration import configuration_time_line
from copy import deepcopy

class ProblemFormulation():
	"""
	Problem formulation class for unit commitment problem in hybrid AC/DC microgrid.
	"""
	def problem_formulation_local(*args):
		"""
		Problem formulation for unit commitment problem (normal state)
		:param model:
		:return:
		"""

		from modelling.data.idx_uc_format import IG, PG, RG, IUG, PUG, RUG, PBIC_AC2DC, PBIC_DC2AC, PESS_C, \
			PESS_DC, RESS, EESS, PMG, NX

		model = deepcopy(args[0])
		T = configuration_time_line.default_look_ahead_time_step["Look_ahead_time_uc_time_step"]
		nx = NX * T
		lb = [0] * NX
		ub = [0] * NX

		vtypes = ["c"] * NX
		vtypes[IG] = "b"
		vtypes[IUG] = "b"
		vtypes = vtypes * T

		## Update lower boundary
		lb[IG] = 0
		lb[PG] = model["DG"]["PMIN"]
		lb[RG] = model["DG"]["PMIN"]

		lb[IUG] = 0
		lb[PUG] = model["UG"]["PMIN"]
		lb[RUG] = model["UG"]["PMIN"]

		lb[PBIC_AC2DC] = 0
		lb[PBIC_DC2AC] = 0

		lb[PESS_C] = 0
		lb[PESS_DC] = 0
		lb[RESS] = 0
		lb[EESS] = model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"]

		lb[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line

		## Update lower boundary
		for i in range(T):
			ub[IG] = model["DG"]["STATUS"][i]
		ub[PG] = model["DG"]["PMAX"]
		ub[RG] = model["DG"]["PMAX"]

		for i in range(T):
			ub[IUG] = model["UG"]["STATUS"][i]
		ub[PUG] = model["UG"]["PMAX"]
		ub[RUG] = model["UG"]["PMAX"]

		ub[PBIC_AC2DC] = model["BIC"]["SMAX"]
		ub[PBIC_DC2AC] = model["BIC"]["SMAX"]

		ub[PESS_C] = model["ESS"]["PMAX_CH"]
		ub[PESS_DC] = model["ESS"]["PMAX_DIS"]
		ub[RESS] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]
		ub[EESS] = model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"]

		ub[PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line
		# Finalize the boundary information
		LB = lb * T
		UB = ub * T

		## Constraints set
		# 1) Power balance equation
		Aeq = zeros((T, nx))
		beq = [ ]
		for i in range(T):
			Aeq[i][i * NX + PG] = 1
			Aeq[i][i * NX + PUG] = 1
			Aeq[i][i * NX + PBIC_AC2DC] = -1
			Aeq[i][i * NX + PBIC_DC2AC] = model["BIC"]["EFF_DC2AC"]
			beq.append(model["Load_ac"]["PD"][i] + model["Load_nac"]["PD"][i])
		# 2) DC power balance equation
		Aeq_temp = zeros((T, nx))
		for i in range(T):
			Aeq_temp[i][i * NX + PBIC_AC2DC] = model["BIC"]["EFF_AC2DC"]
			Aeq_temp[i][i * NX + PBIC_DC2AC] = -1
			Aeq_temp[i][i * NX + PESS_C] = -1
			Aeq_temp[i][i * NX + PESS_DC] = 1
			Aeq_temp[i][i * NX + PMG] = -1
			beq.append(
				model["Load_dc"]["PD"][i] + model["Load_ndc"]["PD"][i] - model["PV"]["PG"][i] - model["WP"]["PG"][i])

		Aeq = vstack([Aeq, Aeq_temp])

		# 3) Energy storage system
		Aeq_temp = zeros((T, nx))
		for i in range(T):
			if i == 0:
				Aeq_temp[i][i * NX + EESS] = 1
				Aeq_temp[i][i * NX + PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				Aeq_temp[i][i * NX + PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				beq.append(model["ESS"]["SOC"] * model["ESS"]["CAP"])
			else:
				Aeq_temp[i][(i - 1) * NX + EESS] = -1
				Aeq_temp[i][i * NX + EESS] = 1
				Aeq_temp[i][i * NX + PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				Aeq_temp[i][i * NX + PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				beq.append(0)
		Aeq = vstack([Aeq, Aeq_temp])
		# 4) Energy storage system
		Aeq_temp = zeros((1, nx))
		Aeq_temp[0][(T-1)*NX+EESS] = 1
		Aeq = vstack([Aeq, Aeq_temp])
		beq.append(model["ESS"]["SOC"] * model["ESS"]["CAP"])

		# Inequality constraints
		# 1) PG + RG <= IG*PGMAX
		Aineq = zeros((T, nx))
		bineq = []
		for i in range(T):
			Aineq[i][i * NX + PG] = 1
			Aineq[i][i * NX + RG] = 1
			Aineq[i][i * NX + IG] = -model["DG"]["PMAX"]
			bineq.append(0)
		# 2) PG - RG >= IG*PGMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PG] = -1
			Aineq_temp[i][i * NX + RG] = 1
			Aineq_temp[i][i * NX + IG] = model["DG"]["PMIN"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 3) PUG + RUG <= PUGMAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PUG] = 1
			Aineq_temp[i][i * NX + RUG] = 1
			Aineq_temp[i][i * NX + IUG] = -model["UG"]["PMAX"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 4) PUG - RUG >= PUGMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PUG] = -1
			Aineq_temp[i][i * NX + RUG] = 1
			Aineq_temp[i][i * NX + IUG] = model["UG"]["PMIN"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 5) PESS_DC - PESS_C + RESS <= PESS_DC_MAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_DC] = 1
			Aineq_temp[i][i * NX + PESS_C] = -1
			Aineq_temp[i][i * NX + RESS] = 1
			bineq.append(model["ESS"]["PMAX_DIS"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 6) PESS_DC - PESS_C - RESS >= -PESS_C_MAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_DC] = -1
			Aineq_temp[i][i * NX + PESS_C] = 1
			Aineq_temp[i][i * NX + RESS] = 1
			bineq.append(model["ESS"]["PMAX_CH"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 7) EESS - RESS*delta >= EESSMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + EESS] = -1
			Aineq_temp[i][i * NX + RESS] = configuration_time_line.default_time["Time_step_uc"] / 3600
			bineq.append(-model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 8) EESS + RESS*delta <= EESSMAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + EESS] = 1
			Aineq_temp[i][i * NX + RESS] = configuration_time_line.default_time["Time_step_uc"] / 3600
			bineq.append(model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 9) RG + RUG + RESS >= sum(Load)*beta + sum(PV)*beta_pv + sum(WP)*beta_wp
		# No reserve requirement
		# 10） IG+IUG<=1
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + IG] = 1
			Aineq_temp[i][i * NX + IUG] = 1
			bineq.append(1)
		Aineq = vstack([Aineq, Aineq_temp])

		c = [0] * NX
		if model["DG"]["COST_MODEL"] == 2:
			c[PG] = model["DG"]["COST"][1]
		else:
			c[PG] = model["DG"]["COST"][0]

		c[IG] = model["DG"]["COST_START_UP"]
		c[PUG] = model["UG"]["COST"][0]
		c[IUG] = model["UG"]["COST_START_UP"]
		c[PESS_C] = model["ESS"]["COST_CH"][0]
		c[PESS_DC] = model["ESS"]["COST_DIS"][0]
		C = c * T
		# Generate the quadratic parameters
		Q = zeros((nx, nx))
		for i in range(T):
			if model["DG"]["COST_MODEL"] == 2:
				Q[i * NX + PG][i * NX + PG] = model["DG"]["COST"][1]

		mathematical_model = {"Q": Q,
							  "c": C,
							  "Aeq": Aeq,
							  "beq": beq,
							  "A": Aineq,
							  "b": bineq,
							  "lb": LB,
							  "ub": UB,
							  "vtypes": vtypes}

		return mathematical_model

	def problem_formulation_local_recovery(*args):
		"""
		Problem formulation for unit commitment problem (emergency state)
		:param model: information model
		:return:
		"""
		from modelling.data.idx_uc_recovery_format import IG, PG, RG, IUG, PUG, RUG, IBIC, PBIC_AC2DC, PBIC_DC2AC, \
			IESS, PESS_C, PESS_DC, RESS, EESS, PMG, IPV, IWP, IL_AC, IL_NAC, IL_DC, IL_NDC, NX
		model = deepcopy(args[0])

		T = configuration_time_line.default_look_ahead_time_step["Look_ahead_time_uc_time_step"]
		nx = T * NX
		lb = [0] * nx
		ub = [0] * nx
		vtypes = ["c"] * nx
		for i in range(T):
			## Update lower boundary
			lb[i * NX + IG] = 0
			vtypes[i * NX + IG] = "b"
			lb[i * NX + PG] = model["DG"]["PMIN"]
			lb[i * NX + RG] = model["DG"]["PMIN"]
			lb[i * NX + IUG] = 0
			vtypes[i * NX + IUG] = "b"
			lb[i * NX + IBIC] = 0
			lb[i * NX + PUG] = model["UG"]["PMIN"]
			lb[i * NX + RUG] = model["UG"]["PMIN"]
			vtypes[i * NX + IBIC] = "b"
			lb[i * NX + PBIC_AC2DC] = 0
			lb[i * NX + PBIC_DC2AC] = 0
			vtypes[i * NX + IESS] = "b"
			lb[i * NX + IESS] = 0
			lb[i * NX + PESS_C] = 0
			lb[i * NX + PESS_DC] = 0
			lb[i * NX + RESS] = 0
			lb[i * NX + EESS] = model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"]
			lb[i * NX + PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line
			lb[i * NX + IPV] = 0
			lb[i * NX + IWP] = 0
			lb[i * NX + IL_AC] = 0
			lb[i * NX + IL_NAC] = 0
			lb[i * NX + IL_DC] = 0
			lb[i * NX + IL_NDC] = 0
			## Update lower boundary
			ub[i * NX + IG] = model["DG"]["STATUS"][i]
			ub[i * NX + PG] = model["DG"]["PMAX"]
			ub[i * NX + RG] = model["DG"]["PMAX"]
			ub[i * NX + IUG] = model["UG"]["STATUS"][i]
			ub[i * NX + PUG] = model["UG"]["PMAX"]
			ub[i * NX + RUG] = model["UG"]["PMAX"]
			ub[i * NX + IBIC] = 1
			ub[i * NX + PBIC_AC2DC] = model["BIC"]["SMAX"]
			ub[i * NX + PBIC_DC2AC] = model["BIC"]["SMAX"]
			ub[i * NX + IESS] = 1
			ub[i * NX + PESS_C] = model["ESS"]["PMAX_CH"]
			ub[i * NX + PESS_DC] = model["ESS"]["PMAX_DIS"]
			ub[i * NX + RESS] = model["ESS"]["PMAX_DIS"] + model["ESS"]["PMAX_CH"]
			ub[i * NX + EESS] = model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"]
			ub[i * NX + PMG] = 0  # The line flow limitation, the predefined status is, the transmission line is off-line
			ub[i * NX + IPV] = model["PV"]["PG"][i]
			ub[i * NX + IWP] = model["WP"]["PG"][i]
			ub[i * NX + IL_AC] = model["Load_ac"]["PD"][i]
			ub[i * NX + IL_NAC] = model["Load_nac"]["PD"][i]
			ub[i * NX + IL_DC] = model["Load_dc"]["PD"][i]
			ub[i * NX + IL_NDC] = model["Load_ndc"]["PD"][i]

		## Constraints set
		# 1) Power balance equation
		Aeq = zeros((T, nx))
		beq = []
		for i in range(T):
			Aeq[i][i * NX + PG] = 1
			Aeq[i][i * NX + PUG] = 1
			Aeq[i][i * NX + PBIC_AC2DC] = -1
			Aeq[i][i * NX + PBIC_DC2AC] = model["BIC"]["EFF_DC2AC"]
			Aeq[i][i * NX + IL_AC] = -1
			Aeq[i][i * NX + IL_NAC] = -1
			beq.append(0)
		# 2) DC power balance equation
		Aeq_temp = zeros((T, nx))
		for i in range(T):
			Aeq_temp[i][i * NX + PBIC_AC2DC] = model["BIC"]["EFF_AC2DC"]
			Aeq_temp[i][i * NX + PBIC_DC2AC] = -1
			Aeq_temp[i][i * NX + PESS_C] = -1
			Aeq_temp[i][i * NX + PESS_DC] = 1
			Aeq_temp[i][i * NX + PMG] = -1
			Aeq_temp[i][i * NX + IL_DC] = -1
			Aeq_temp[i][i * NX + IL_NDC] = -1
			Aeq_temp[i][i * NX + IPV] = 1
			Aeq_temp[i][i * NX + IWP] = 1
			beq.append(0)
		Aeq = vstack([Aeq, Aeq_temp])

		# 3) Energy storage system
		# 3) Energy storage system
		Aeq_temp = zeros((T, nx))
		for i in range(T):
			if i == 0:
				Aeq_temp[i][i * NX + EESS] = 1
				Aeq_temp[i][i * NX + PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				Aeq_temp[i][i * NX + PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				beq.append(model["ESS"]["SOC"] * model["ESS"]["CAP"])
			else:
				Aeq_temp[i][(i - 1) * NX + EESS] = -1
				Aeq_temp[i][i * NX + EESS] = 1
				Aeq_temp[i][i * NX + PESS_C] = -model["ESS"]["EFF_CH"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				Aeq_temp[i][i * NX + PESS_DC] = 1 / model["ESS"]["EFF_DIS"] * configuration_time_line.default_time[
					"Time_step_uc"] / 3600
				beq.append(0)
		Aeq = vstack([Aeq, Aeq_temp])

		# Inequality constraints
		# Inequality constraints
		Aineq = zeros((T, nx))
		bineq = []
		for i in range(T):
			Aineq[i][i * NX + PG] = 1
			Aineq[i][i * NX + RG] = 1
			Aineq[i][i * NX + IG] = -model["DG"]["PMAX"]
			bineq.append(0)
		# 2) PG - RG >= IG*PGMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PG] = -1
			Aineq_temp[i][i * NX + RG] = 1
			Aineq_temp[i][i * NX + IG] = model["DG"]["PMIN"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 3) PUG + RUG <= PUGMAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PUG] = 1
			Aineq_temp[i][i * NX + RUG] = 1
			Aineq_temp[i][i * NX + IUG] = -model["UG"]["PMAX"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 4) PUG - RUG >= PUGMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PUG] = -1
			Aineq_temp[i][i * NX + RUG] = 1
			Aineq_temp[i][i * NX + IUG] = model["UG"]["PMIN"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 5) PESS_DC - PESS_C + RESS <= PESS_DC_MAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_DC] = 1
			Aineq_temp[i][i * NX + PESS_C] = -1
			Aineq_temp[i][i * NX + RESS] = 1
			bineq.append(model["ESS"]["PMAX_DIS"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 6) PESS_DC - PESS_C - RESS >= -PESS_C_MAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_DC] = -1
			Aineq_temp[i][i * NX + PESS_C] = 1
			Aineq_temp[i][i * NX + RESS] = 1
			bineq.append(model["ESS"]["PMAX_CH"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 7) EESS - RESS*delta >= EESSMIN
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + EESS] = -1
			Aineq_temp[i][i * NX + RESS] = configuration_time_line.default_time["Time_step_uc"] / 3600
			bineq.append(-model["ESS"]["SOC_MIN"] * model["ESS"]["CAP"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 8) EESS + RESS*delta <= EESSMAX
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + EESS] = 1
			Aineq_temp[i][i * NX + RESS] = configuration_time_line.default_time["Time_step_uc"] / 3600
			bineq.append(model["ESS"]["SOC_MAX"] * model["ESS"]["CAP"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 9) RG + RUG + RESS >= sum(Load)*beta + sum(PV)*beta_pv + sum(WP)*beta_wp
		# 10) PBIC_AC2DC <=IBIC*
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PBIC_AC2DC] = 1
			Aineq_temp[i][i * NX + IBIC] = -model["BIC"]["SMAX"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 11) PBIC_AC2DC <=(1-IBIC)*
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PBIC_DC2AC] = 1
			Aineq_temp[i][i * NX + IBIC] = model["BIC"]["SMAX"]
			bineq.append(model["BIC"]["SMAX"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 12) PBIC_AC2DC <=IBIC*
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_C] = 1
			Aineq_temp[i][i * NX + IESS] = -model["ESS"]["PMAX_CH"]
			bineq.append(0)
		Aineq = vstack([Aineq, Aineq_temp])
		# 13) PBIC_AC2DC <=(1-IBIC)*
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + PESS_DC] = 1
			Aineq_temp[i][i * NX + IESS] = model["ESS"]["PMAX_DIS"]
			bineq.append(model["ESS"]["PMAX_DIS"])
		Aineq = vstack([Aineq, Aineq_temp])
		# 14） IG+IUG<=1
		Aineq_temp = zeros((T, nx))
		for i in range(T):
			Aineq_temp[i][i * NX + IG] = 1
			Aineq_temp[i][i * NX + IUG] = 1
			bineq.append(1)
		Aineq = vstack([Aineq, Aineq_temp])
		# No reserve requirement
		c = [0] * NX
		if model["DG"]["COST_MODEL"] == 2:
			c[PG] = model["DG"]["COST"][1]
		else:
			c[PG] = model["DG"]["COST"][0]
		c[PUG] = model["UG"]["COST"][0]
		c[PESS_C] = model["ESS"]["COST_CH"][0]
		c[PESS_DC] = model["ESS"]["COST_DIS"][0]
		c[IG] = model["DG"]["COST_START_UP"]
		c[IUG] = model["UG"]["COST_START_UP"]
		# The sheding cost
		c[IPV] = -model["PV"]["COST"]
		c[IWP] = -model["WP"]["COST"]
		c[IL_AC] = -model["Load_ac"]["COST"][0]
		c[IL_NAC] = -model["Load_nac"]["COST"][0]
		c[IL_DC] = -model["Load_dc"]["COST"][0]
		c[IL_NDC] = -model["Load_ndc"]["COST"][0]

		C = c * T
		# Generate the quadratic parameters
		Q = zeros((nx, nx))
		for i in range(T):
			if model["DG"]["COST_MODEL"] == 2:
				Q[i * NX + PG][i * NX + PG] = model["DG"]["COST"][1]
		mathematical_model = {"Q": Q,
							  "c": C,
							  "Aeq": Aeq,
							  "beq": beq,
							  "A": Aineq,
							  "b": bineq,
							  "lb": lb,
							  "ub": ub,
							  "vtypes": vtypes}

		return mathematical_model

	def problem_formulation_universal(*args):
		# Formulate mathematical models for different operations
		local_model = deepcopy(args[0])
		universal_model = deepcopy(args[1])
		type = args[len(args) - 1]  # The last one is the type

		T = configuration_time_line.default_look_ahead_time_step["Look_ahead_time_uc_time_step"]

		## Formulating the universal energy models
		if type == "Feasible":
			from modelling.data.idx_uc_format import PMG, NX
			local_model_mathematical = ProblemFormulation.problem_formulation_local(local_model)
			universal_model_mathematical = ProblemFormulation.problem_formulation_local(universal_model)
		else:
			from modelling.data.idx_uc_recovery_format import PMG, NX
			local_model_mathematical = ProblemFormulation.problem_formulation_local_recovery(local_model)
			universal_model_mathematical = ProblemFormulation.problem_formulation_local_recovery(universal_model)
		# Modify the boundary information

		for i in range(T):
			local_model_mathematical["lb"][i * NX + PMG] = -universal_model["LINE"]["STATUS"][i] * universal_model["LINE"]["RATE_A"]
			local_model_mathematical["ub"][i * NX + PMG] = universal_model["LINE"]["STATUS"][i] * universal_model["LINE"]["RATE_A"]
			universal_model_mathematical["lb"][i * NX + PMG] = -universal_model["LINE"]["STATUS"][i] * \
															   universal_model["LINE"]["RATE_A"]
			universal_model_mathematical["ub"][i * NX + PMG] = universal_model["LINE"]["STATUS"][i] * \
															   universal_model["LINE"]["RATE_A"]
		## Modify the matrix
		nx = T * NX
		neq = local_model_mathematical["Aeq"].shape[0]  # Number of equality constraint
		nineq = local_model_mathematical["A"].shape[0]  # Number of inequality constraint
		Aeq_compact = zeros((2 * neq, 2 * nx))
		beq_compact = zeros(2 * neq)
		Aineq_compact = zeros((2 * nineq, 2 * nx))
		bineq_compact = zeros(2 * nineq)
		c_compact = zeros(2 * nx)

		Aeq_compact[0:neq, 0:nx] = local_model_mathematical["Aeq"]
		Aeq_compact[neq:2 * neq, nx:2 * nx] = universal_model_mathematical["Aeq"]
		beq_compact[0:neq] = local_model_mathematical["beq"]
		beq_compact[neq:2 * neq] = universal_model_mathematical["beq"]

		Aineq_compact[0:nineq, 0:nx] = local_model_mathematical["A"]
		Aineq_compact[nineq:2 * nineq, nx:2 * nx] = universal_model_mathematical["A"]
		bineq_compact[0:nineq] = local_model_mathematical["b"]
		bineq_compact[nineq:2 * nineq] = universal_model_mathematical["b"]

		c_compact[0:nx] = local_model_mathematical["c"]
		c_compact[nx:2 * nx] = universal_model_mathematical["c"]
		c_compact = array(c_compact)

		lb = numpy.append(local_model_mathematical["lb"], universal_model_mathematical["lb"])
		ub = numpy.append(local_model_mathematical["ub"], universal_model_mathematical["ub"])
		vtypes = numpy.append(local_model_mathematical["vtypes"], universal_model_mathematical["vtypes"])

		Aeq_compact_temp = zeros((T, 2 * nx))
		for i in range(T):
			Aeq_compact_temp[i][i * NX + PMG] = 1
			Aeq_compact_temp[i][nx + i * NX + PMG] = 1
			beq_compact = numpy.append(beq_compact, zeros(1))
		Aeq_compact = vstack([Aeq_compact, Aeq_compact_temp])

		Q_compact = zeros((2 * nx, 2 * nx))
		Q_compact[0:nx, 0:nx] = local_model_mathematical["Q"]
		Q_compact[nx:2 * nx, nx:2 * nx] = universal_model_mathematical["Q"]

		model = {"Q": Q_compact,
				 "c": c_compact,
				 "Aeq": Aeq_compact,
				 "beq": beq_compact,
				 "A": Aineq_compact,
				 "b": bineq_compact,
				 "lb": lb,
				 "ub": ub,
				 "vtypes": vtypes}
		return model
