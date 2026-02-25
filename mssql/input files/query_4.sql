


CREATE VIEW [MNSReporting].[4P_MobilityData]
WITH SCHEMABINDING
AS

--SELECT  
--		[Consumption Period],		
--		CASE WHEN SUBSTRING([Consumption Period],5,6) = '11' THEN concat((SUBSTRING([Consumption Period],1,4)+1) , '01')
--			 WHEN SUBSTRING([Consumption Period],5,6) = '12' THEN concat((SUBSTRING([Consumption Period],1,4)+1) , '02')
--			 ELSE ([Consumption Period] +2) end as [Calc_Consumption_Period], 
--		[Supplier Name] as SupplierName,
--		[Service Number] as ServiceNumber,
--		[User ID] as UserID,
--		[User Display Name] as [WWDisplayName],
--		[Total Plan Charges in USD] as TotalPlanChargesInUSD,
--		[Total Equipment Charges in USD] as TotalEquipmentChargesInUSD,
--		[Total National Charges in USD] as TotalNationalChargesInUSD ,
--		[Total International Charges in USD] as TotalInternationalChargesInUSD,
--		[Total Roaming Charges in USD] as TotalRoamingChargesInUSD,
--		[Total Data Charges in USD] as TotalDataChargesInUSD,
--		[Total Misc Charges in USD] as TotalMiscChargesInUSD,
--		[Amount before Tax USD] as [AmountbeforeTaxUSD],
--		[Call Duration in Minutes] as [CallDurationInMinutes],
--		[Data Usage in MB] as [DataUsageInMB],
--		[IT Business] as [ITBusiness],
--		[IT Country] as [ITCountry],
--		[IT Country (abbr)] as [ITCountryAbbr],
--		[GIDUser Business] as [GIDUserBusiness],
--		[GIDUser Country] as [GIDUserCountry],
--		[GIDUser ADCountry] as [GIDUserADCountry],
--		[GIDUser WWEmployeeType] as [GIDUserWWEmployeeType],
--		[GIDUser E-mail] as [GIDUserEmail],
--		[GIDUser mobile] as [GIDUserMobile],
--		[GIDUser mobile-clean] as [GIDUser mobile-clean],
--		[GIDUser mobile-clean(9)] as [GIDUser mobile-clean(9)],
--		[GIDUser department] as [GIDUserDepartment],
--		[GIDUser OU] as [GIDUserOU],
--		[GIDUser RefInd] as [GIDUserRefInd],
--		[GIDUser Location] as [GIDUserLocation],
--		[GIDUser CustomerLevel1] as [GIDUSerCustomerLevel1],
--		[GIDUser CustomerLevel2] as [GIDUSerCustomerLevel2],
--		[GIDUser CustomerLevel3] as [GIDUSerCustomerLevel3]
--	FROM
--	[MNS].[Shell_Business_Mobility_Detailed]
--	where 
--	[Consumption Period] >= (select LEFT(CONVERT(varchar, dateadd(m,-8,GetDate()),112),6)) 

	Select [Consumption Period], [GIDUser Business] as [GIDUserBusiness], [GIDUser CustomerLevel1] as [GIDUSerCustomerLevel1],[GIDUser CustomerLevel2] as [GIDUSerCustomerLevel2],[GIDUser CustomerLevel3] as [GIDUSerCustomerLevel3], sum(Cast([Amount before Tax USD] as money)) as Amount from [MNS].[Shell_Business_Mobility_Detailed] 
	where 
	([Consumption Period] in ('201912','202012') 
	or [Consumption Period] >= (select LEFT(CONVERT(varchar, dateadd(m,-6,GetDate()),112),6))
	)
	group by [Consumption Period], [GIDUser Business], [GIDUser CustomerLevel1], [GIDUser CustomerLevel2], [GIDUser CustomerLevel3]  --added newly on 15/03/2021

