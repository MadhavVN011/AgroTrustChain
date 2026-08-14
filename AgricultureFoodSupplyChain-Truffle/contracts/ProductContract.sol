pragma solidity >=0.4.22 <0.9.0;
    contract ProductContract {
    string public agricultureBoardID;
	string public buyerID;
	string public farmerID;
	string public productID;
	int public price;
	int public qty;
	
    
    function perform_transactions(string memory _agricultureBoardID, string memory _buyerID, string memory _farmerID, string memory _productID, int _price, int _qty) public{
       agricultureBoardID = _agricultureBoardID;
		buyerID = _buyerID;
		farmerID = _farmerID;
		productID = _productID;
		price = _price;
		qty = _qty;
		
    }
        
}
